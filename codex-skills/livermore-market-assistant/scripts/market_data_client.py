from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import akshare as ak
except Exception:  # pragma: no cover
    ak = None


SKILL_ROOT = Path(__file__).resolve().parents[1]
LOOKUP_CACHE_PATH = SKILL_ROOT / 'assets' / 'stock_lookup_cache.json'
CN_INDEX_NAMES = [
    '上证指数',
    '深证成指',
    '创业板指',
    '沪深300',
    '科创50',
]
COMMON_TEXT_PREFIXES = (
    '我昨天买了',
    '我买了',
    '我持有',
    '昨天买了',
    '今天买了',
    '持有',
    '买了',
    '关注',
    '看好',
    '拿着',
    '仓位在',
)
STOP_PHRASES = (
    '今天A股这种盘面',
    '明天应该偏向持有',
    '减仓还是等确认',
    '板块龙头是谁',
    '明天怎么操作',
)


@dataclass
class CacheItem:
    value: Any
    expires_at: float


class MarketDataClient:
    def __init__(self) -> None:
        self._cache: dict[str, CacheItem] = {}
        self._lock = threading.Lock()

    def available(self) -> bool:
        return ak is not None

    def get_market_overview(self) -> dict[str, Any]:
        if ak is None:
            return {'available': False, 'message': '实时行情依赖未安装。', 'indices': []}

        try:
            df = self._cached('cn_indices', 30, ak.stock_zh_index_spot_sina)
        except Exception as exc:
            return {'available': False, 'message': f'实时行情暂时不可用：{exc}', 'indices': []}

        rows: list[dict[str, Any]] = []
        for index_name in CN_INDEX_NAMES:
            matched = df[df['名称'].astype(str) == index_name]
            if matched.empty:
                continue
            row = matched.iloc[0]
            rows.append(
                {
                    'name': str(row['名称']),
                    'price': self._to_float(row['最新价']),
                    'pct': self._to_float(row['涨跌幅']),
                    'change': self._to_float(row['涨跌额']),
                }
            )
        return {'available': True, 'message': '', 'indices': rows, 'updated_at': time.strftime('%H:%M:%S')}

    def resolve_stock(self, text: str) -> dict[str, str] | None:
        if ak is None or not text.strip():
            return None

        direct_code = re.search(r'(?<!\d)(\d{6})(?!\d)', text)
        if direct_code:
            code = direct_code.group(1)
            names_df = self._stock_lookup_table()
            matched = names_df[names_df['code'].astype(str) == code]
            if not matched.empty:
                row = matched.iloc[0]
                return {'code': str(row['code']), 'name': str(row['name'])}
            return {'code': code, 'name': code}

        cleaned_text = self._clean_text(text)
        names_df = self._stock_lookup_table()

        contains_alias = names_df[names_df['alias'].astype(str).apply(lambda item: bool(item) and item in cleaned_text)]
        if not contains_alias.empty:
            ranked = contains_alias.assign(
                alias_len=contains_alias['alias'].astype(str).str.len(),
                name_len=contains_alias['name'].astype(str).str.len(),
            ).sort_values(['alias_len', 'name_len'], ascending=[False, True])
            row = ranked.iloc[0]
            return {'code': str(row['code']), 'name': str(row['name'])}

        for candidate in self._extract_stock_candidates(cleaned_text):
            exact = names_df[names_df['alias'].astype(str) == candidate]
            if not exact.empty:
                row = exact.iloc[0]
                return {'code': str(row['code']), 'name': str(row['name'])}

            fuzzy = names_df[names_df['alias'].astype(str).str.contains(candidate, regex=False, na=False)]
            if not fuzzy.empty:
                ranked = fuzzy.assign(alias_len=fuzzy['alias'].astype(str).str.len()).sort_values('alias_len')
                row = ranked.iloc[0]
                return {'code': str(row['code']), 'name': str(row['name'])}
        return None

    def get_stock_snapshot(self, text: str) -> dict[str, Any] | None:
        resolved = self.resolve_stock(text)
        if not resolved:
            return None
        code = resolved['code']

        quote_df = None
        info_df = None
        errors: list[str] = []
        try:
            quote_df = self._cached(f'stock_bid_ask:{code}', 20, lambda: ak.stock_bid_ask_em(symbol=code))
        except Exception as exc:
            errors.append(f'quote:{exc}')
        try:
            info_df = self._cached(f'stock_info:{code}', 24 * 3600, lambda: ak.stock_individual_info_em(symbol=code))
        except Exception as exc:
            errors.append(f'info:{exc}')

        if quote_df is None and info_df is None:
            return {'name': resolved['name'], 'code': code, 'available': False, 'message': '; '.join(errors)}

        quote_map = {} if quote_df is None else dict(zip(quote_df['item'].astype(str), quote_df['value']))
        info_map = {} if info_df is None else dict(zip(info_df['item'].astype(str), info_df['value']))
        return {
            'available': True,
            'quote_available': quote_df is not None,
            'info_available': info_df is not None,
            'message': '; '.join(errors),
            'name': str(info_map.get('股票简称') or resolved['name']),
            'code': code,
            'latest': self._to_float(quote_map.get('最新') or info_map.get('最新')),
            'pct': self._to_float(quote_map.get('涨幅')),
            'change': self._to_float(quote_map.get('涨跌')),
            'open': self._to_float(quote_map.get('今开')),
            'high': self._to_float(quote_map.get('最高')),
            'low': self._to_float(quote_map.get('最低')),
            'prev_close': self._to_float(quote_map.get('昨收')),
            'turnover': self._to_float(quote_map.get('换手')),
            'amount': self._to_float(quote_map.get('金额')),
            'volume': self._to_float(quote_map.get('总手')),
            'industry': str(info_map.get('行业') or ''),
        }

    def get_industry_board(self, industry: str) -> dict[str, Any]:
        industry = str(industry or '').strip()
        if not industry:
            return {'available': False, 'message': '没有可用的行业标签。'}
        if ak is None:
            return {'available': False, 'message': '实时行情依赖未安装。'}

        try:
            boards = self._cached('industry_boards', 90, ak.stock_board_industry_name_em)
        except Exception as exc:
            return {'available': False, 'message': f'行业板块快照暂时不可用：{exc}'}

        exact = boards[boards['板块名称'].astype(str) == industry]
        if exact.empty:
            exact = boards[
                boards['板块名称'].astype(str).str.contains(industry, regex=False, na=False)
                | boards['板块名称'].astype(str).apply(lambda item: item in industry if item else False)
            ]
        if exact.empty:
            return {'available': False, 'message': f'未在行业板块列表里匹配到 {industry}。'}

        row = exact.iloc[0]
        return {
            'available': True,
            'board_name': str(row['板块名称']),
            'pct': self._to_float(row['涨跌幅']),
            'change': self._to_float(row['涨跌额']),
            'leader': str(row['领涨股票']),
            'leader_pct': self._to_float(row['领涨股票-涨跌幅']),
            'up_count': self._to_int(row['上涨家数']),
            'down_count': self._to_int(row['下跌家数']),
        }

    def _stock_lookup_table(self):
        return self._cached('stock_lookup_table', 24 * 3600, self._build_stock_lookup_table)

    def _build_stock_lookup_table(self):
        import pandas as pd

        frames = []
        errors: list[Exception] = []
        try:
            base = ak.stock_info_a_code_name()
            base = base.rename(columns={'code': 'code', 'name': 'name'})
            base['alias'] = base['name']
            frames.append(base[['code', 'name', 'alias']])
        except Exception as exc:
            errors.append(exc)

        for loader in (self._load_sh_lookup, self._load_sz_lookup, self._load_bj_lookup):
            try:
                frame = loader()
            except Exception as exc:
                errors.append(exc)
                frame = None
            if frame is not None and not frame.empty:
                frames.append(frame[['code', 'name', 'alias']])

        if frames:
            lookup = pd.concat(frames, ignore_index=True)
            lookup['code'] = lookup['code'].astype(str)
            lookup['name'] = lookup['name'].astype(str).str.strip()
            lookup['alias'] = lookup['alias'].astype(str).str.strip()
            lookup = lookup[lookup['alias'] != '']
            lookup = lookup.drop_duplicates(subset=['code', 'alias']).reset_index(drop=True)
            self._save_lookup_cache(lookup)
            return lookup

        cached = self._load_lookup_cache()
        if cached is not None:
            return cached
        if errors:
            raise errors[0]
        raise RuntimeError('Unable to build stock lookup table')

    def _load_sh_lookup(self):
        rows = []
        df = ak.stock_info_sh_name_code()
        for _, row in df.iterrows():
            code = str(row.get('证券代码') or '').strip()
            name = str(row.get('证券简称') or row.get('公司简称') or '').strip()
            aliases = [
                str(row.get('证券简称') or '').strip(),
                str(row.get('证券全称') or '').strip(),
                str(row.get('公司简称') or '').strip(),
                str(row.get('公司全称') or '').strip(),
            ]
            for alias in aliases:
                if code and name and alias:
                    rows.append({'code': code, 'name': name, 'alias': alias})
        return self._rows_to_frame(rows)

    def _load_sz_lookup(self):
        rows = []
        df = ak.stock_info_sz_name_code()
        for _, row in df.iterrows():
            code = str(row.get('A股代码') or '').strip()
            name = str(row.get('A股简称') or '').strip()
            if code and name:
                rows.append({'code': code, 'name': name, 'alias': name})
        return self._rows_to_frame(rows)

    def _load_bj_lookup(self):
        rows = []
        df = ak.stock_info_bj_name_code()
        for _, row in df.iterrows():
            code = str(row.get('证券代码') or '').strip()
            name = str(row.get('证券简称') or '').strip()
            if code and name:
                rows.append({'code': code, 'name': name, 'alias': name})
        return self._rows_to_frame(rows)

    @staticmethod
    def _rows_to_frame(rows: list[dict[str, str]]):
        import pandas as pd

        return pd.DataFrame(rows, columns=['code', 'name', 'alias'])

    def _load_lookup_cache(self):
        try:
            import pandas as pd

            if LOOKUP_CACHE_PATH.exists():
                data = json.loads(LOOKUP_CACHE_PATH.read_text(encoding='utf-8'))
                return pd.DataFrame(data, columns=['code', 'name', 'alias'])
        except Exception:
            return None
        return None

    def _save_lookup_cache(self, lookup) -> None:
        try:
            LOOKUP_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            payload = lookup[['code', 'name', 'alias']].to_dict(orient='records')
            LOOKUP_CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            return

    def _extract_stock_candidates(self, text: str) -> list[str]:
        raw = re.findall(r'[\u4e00-\u9fffA-Za-z0-9]{2,16}', text)
        cleaned: list[str] = []
        for item in raw:
            candidate = item.strip()
            for prefix in COMMON_TEXT_PREFIXES:
                if candidate.startswith(prefix):
                    candidate = candidate[len(prefix):]
            if candidate and candidate not in STOP_PHRASES and not candidate.isdigit():
                cleaned.append(candidate)
        seen: set[str] = set()
        result: list[str] = []
        for item in cleaned:
            if item not in seen:
                seen.add(item)
                result.append(item)
        result.sort(key=len, reverse=True)
        return result[:12]

    @staticmethod
    def _clean_text(text: str) -> str:
        cleaned = re.sub(r'[，。！？?、,.!:\-\(\)（）\[\]【】/\\]+', ' ', text)
        return re.sub(r'\s+', ' ', cleaned).strip()

    def _cached(self, key: str, ttl_seconds: int, loader):
        now = time.time()
        with self._lock:
            cached = self._cache.get(key)
            if cached and cached.expires_at > now:
                return cached.value
        value = loader()
        with self._lock:
            self._cache[key] = CacheItem(value=value, expires_at=now + ttl_seconds)
        return value

    @staticmethod
    def _to_float(value: Any) -> float | None:
        try:
            if value in ('', None, '-'):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            if value in ('', None, '-'):
                return None
            return int(float(value))
        except (TypeError, ValueError):
            return None

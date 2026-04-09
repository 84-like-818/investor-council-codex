# 自动化调度示例

## Windows 任务计划程序

可以每天或每周执行：

```powershell
cd E:\livermore-harvest-system
RUN_WINDOWS.cmd
```

## macOS / Linux cron

每天凌晨 3 点执行：

```cron
0 3 * * * cd /path/to/livermore-harvest-system && bash run.sh
```

## 推荐节奏

- 公开来源：每周跑 1 次
- 新增本地资料：每次丢进 `incoming_manual/` 后立刻重跑
- 重点缺失项：修改 manifest 后立刻重跑

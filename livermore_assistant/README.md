# 利弗莫尔市场助手

这是一个面向中文用户的本地化投资助手产品原型。

它会把两类能力结合在一起：

- Jesse Livermore 蒸馏语料形成的交易框架
- 实时 A 股指数与个股快照

整个产品默认本地运行，不依赖外部大模型 API，也不会在界面里展示语料库明细。

## 功能特点

- 中文界面与中文回答
- 专业化头像与产品式布局
- 实时 A 股指数快照
- A 股个股名称或代码识别
- 利弗莫尔风格的趋势、仓位、节奏判断
- 本地启动，适合研究、陪练和复盘

## 你自己电脑上怎么用

第一次使用：

```cmd
双击 INSTALL_LIVERMORE_ASSISTANT.cmd
```

以后直接启动：

```cmd
双击 RUN_LIVERMORE_ASSISTANT.cmd
```

启动后浏览器会自动打开：

```text
http://127.0.0.1:8766
```

## 发给别人怎么用

如果你想把它当成产品发给别人：

```cmd
双击 BUILD_LIVERMORE_PRODUCT.cmd
```

打包完成后，把下面这个文件夹整个发给对方：

```text
dist\LivermoreAssistantCN
```

对方电脑上直接双击以下任意一个文件即可：

```text
START_LIVERMORE_ASSISTANT.cmd
LivermoreAssistantCN.exe
```

这种方式不需要对方懂 Python，也不需要他们自己安装项目源码依赖。

## 当前实时行情范围

当前版本已经接入：

- A 股主要指数实时快照
- A 股个股名称 / 代码识别与快照

更偏中国市场的盘前、盘中、复盘讨论。

## 数据与资源位置

- Web 界面：`livermore_assistant/web`
- 服务端：`livermore_assistant/app.py`
- 行情接入：`livermore_assistant/market_data.py`
- Livermore 语料：`jesse-livermore`

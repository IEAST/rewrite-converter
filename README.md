# rewrite-converter

把一份规则转换成 Quantumult X、Loon 和 Shadowrocket 配置的无依赖 Python 工具。

项目的核心不是“把 QX 文本替换成 Loon 文本”，而是：

```text
QX 输入 ──解析──> 统一 Manifest ──校验──> QX / Loon / Shadowrocket
手写 JSON ────────┘
```

统一 Manifest 才是项目的事实来源。生成文件应该随时可以删除和重建，不应手工修改。

## 1. 为什么需要中间格式

三个客户端表达同一功能时，关键词、参数顺序、脚本声明和 MITM 语法可能不同。如果直接进行字符串替换，会遇到三个问题：

1. 无法判断一条规则的真实语义。
2. 目标客户端不支持某项功能时容易静默丢失。
3. 每增加一个客户端，都要编写它与其他所有客户端之间的转换。

使用中间格式后，新增客户端只需增加一个 emitter：

```text
N 个客户端：直接互转需要 N × (N - 1) 条路径
N 个客户端：使用 IR 只需要 N 个 parser + N 个 emitter
```

## 2. 环境要求

- Python 3.9 或更高版本
- 不需要 pip 安装任何第三方包

检查环境：

```bash
python3 --version
```

克隆或下载项目后，进入项目根目录：

```bash
cd rewrite-converter
```

## 3. 第一次运行

运行测试：

```bash
make test
```

生成 Google Redirect 示例：

```bash
make demo
```

输出位于 `generated/`：

```text
generated/google-redirect.conf    # Quantumult X
generated/google-redirect.plugin  # Loon
generated/google-redirect.module  # Shadowrocket
```

## 4. 两种使用方式

### 方式 A：从 QX 配置导入

```bash
PYTHONPATH=src python3 -m rewrite_converter import-qx \
  examples/google-redirect.qx.conf \
  -o rules/google-redirect.json
```

这个命令只完成“解析和标准化”，不会直接生成客户端配置。这样你可以先审查 JSON。

### 方式 B：直接编写 Manifest

参照 [examples/google-redirect.json](examples/google-redirect.json)。最小示例：

```json
{
  "name": "Google Redirect",
  "rewrites": [
    {
      "pattern": "^https?:\\/\\/(www\\.)?(g|google)\\.cn",
      "action": "redirect",
      "status": 302,
      "target": "https://www.google.com"
    }
  ],
  "mitm": {
    "hostnames": ["g.cn", "google.cn", "www.g.cn", "www.google.cn"]
  }
}
```

没有出现的可选字段会使用默认值。

## 5. 校验 Manifest

通用校验：

```bash
PYTHONPATH=src python3 -m rewrite_converter validate rules/google-redirect.json
```

针对 Loon 检查：

```bash
PYTHONPATH=src python3 -m rewrite_converter validate \
  rules/google-redirect.json --target loon
```

诊断分为两类：

- `ERROR`：不能安全生成目标文件，命令返回非零状态。
- `WARNING`：可以生成，但需要人工确认客户端版本或语义。

## 6. 生成单个客户端

```bash
PYTHONPATH=src python3 -m rewrite_converter generate \
  rules/google-redirect.json \
  --target loon \
  -o generated/google-redirect.plugin
```

`--target` 可选值：

- `qx`
- `loon`
- `shadowrocket`

## 7. 一次生成全部客户端

```bash
PYTHONPATH=src python3 -m rewrite_converter generate-all \
  examples/google-redirect.json \
  -o generated
```

## 8. 批量导入上游 QX 仓库

假设上游仓库位于 `<UPSTREAM_REPO>`：

```bash
PYTHONPATH=src python3 -m rewrite_converter import-qx-tree \
  <UPSTREAM_REPO> \
  -o rules
```

目录结构会被保留：

```text
<UPSTREAM_REPO>/AdBlock/AmapAds.conf
                 ↓
rules/AdBlock/AmapAds.json
```

每个不支持的输入行都会成为 warning，并写入对应 Manifest 的 `warnings` 字段。不要在 warning 未处理时宣称转换完成。

## 9. 当前支持的统一动作

### Redirect

```json
{
  "pattern": "^https://example.com",
  "action": "redirect",
  "status": 302,
  "target": "https://target.example"
}
```

### Reject

```json
{
  "pattern": "^https://ads.example",
  "action": "reject",
  "reject_type": "reject-200"
}
```

支持 `reject`、`reject-200`、`reject-dict`、`reject-array`、`reject-img`。

### Request/Response Script

```json
{
  "pattern": "^https://api.example",
  "action": "script-response",
  "script": "https://example.com/script.js",
  "requires_body": true,
  "timeout": 30,
  "tag": "Example Script"
}
```

请求侧使用 `script-request`。

### JSON JQ Response

```json
{
  "pattern": "^https://api.example",
  "action": "json-jq-response",
  "expression": "'del(.ads)'",
  "requires_body": true
}
```

QX 和 Loon 可以生成对应语法。Shadowrocket 暂无经过验证的等价语法，因此针对 Shadowrocket 校验会报错，而不是静默忽略。

## 10. 真实仓库验证结果

使用 `ddgksf2013/Rewrite` 的 34 个 `.conf` 文件进行过测试：

- 已解析：369 条规则
- 明确不支持：5 条规则
- 测试用的上游提交：以执行审计时下载到本地的仓库 HEAD 为准

剩余特殊类型包括：

- QX `response-body ... response-body ...`
- QX `request-body ... request-body ...`
- `script-echo-response`
- QX `request-header ... request-header ...`

这些操作必须先在统一模型中定义语义，再为每个客户端确认能力。不能只改变关键词。

## 11. 怎样新增一种 QX 语法

以新增动作 `example-action` 为例：

1. 在 `model.py` 的 `Action` 中增加动作。
2. 给 `RewriteRule` 增加需要的结构化字段。
3. 在 `parsers/quantumultx.py` 中增加正则和解析逻辑。
4. 在 `validator.py` 中定义字段约束和客户端能力。
5. 分别在三个 emitter 中实现输出；无法支持的目标必须报错。
6. 在 `tests/` 中增加解析、生成和失败路径测试。
7. 对真实上游仓库重新运行批量审计。

## 12. 怎样判断一次转换是安全的

至少完成以下检查：

1. 导入时没有未解释的 warning。
2. `validate --target ...` 没有 error。
3. 正则表达式能够编译。
4. HTTPS 匹配域名出现在 MITM hostname 中。
5. 脚本需要 body 时正确设置 `requires_body`。
6. 脚本自身没有使用目标客户端不支持的 JavaScript API。
7. 在真实设备上检查请求记录和脚本日志。

自动转换器可以证明结构和已知语法，但不能替代设备上的行为验证。

## 13. 项目结构

```text
src/rewrite_converter/
├── model.py                 # 统一中间模型
├── manifest.py              # JSON 读写
├── validator.py             # 通用与目标能力校验
├── cli.py                   # 命令行入口
├── parsers/
│   └── quantumultx.py       # QX 输入适配器
└── emitters/
    ├── quantumultx.py
    ├── loon.py
    └── shadowrocket.py
```

## 14. 下一阶段建议

推荐按以下顺序扩展：

1. 完成剩余 5 条 QX 特殊语法。
2. 增加 JavaScript API 静态扫描器。
3. 增加 Manifest JSON Schema。
4. 增加上游 Git commit 锁定与变更报告。
5. 加入 CI，在每次提交时运行测试和真实样本审计。

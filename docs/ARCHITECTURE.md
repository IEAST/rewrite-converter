# 架构说明

## 数据流

```text
Source text
   │
   ▼
Parser ──> Manifest ──> Validator ──> Emitter ──> Generated profile
                │             │
                └── warnings ─┘
```

### Parser

Parser 只回答：“输入表达了什么？”它不应包含 Loon 或 Shadowrocket 的输出逻辑。

### Manifest

Manifest 保存语义，不保存客户端语法。例如使用：

```json
{"action": "redirect", "status": 302, "target": "https://example.com"}
```

而不是保存 QX 的 `url 302` 字符串。

### Validator

Validator 分两层：

- 通用完整性：正则是否合法、redirect 是否有 target。
- 目标能力：目标客户端能否等价表达该动作。

### Emitter

Emitter 是纯生成器。同一个 Manifest 输入应始终产生相同输出。它不读取网络，也不修改 Manifest。

## 为什么 JSON 优先

YAML 更适合人工编辑，但 Python 标准库没有 YAML 解析器。第一版选择 JSON，可以做到零依赖和严格解析。未来可以新增 YAML parser，但内部 Manifest 不需要改变。

## 不静默降级

如果目标客户端不支持一个动作，正确行为是 error，而不是：

- 忽略该规则；
- 输出一条注释后仍返回成功；
- 猜测一个“差不多”的语法。

生成配置的可信度比生成数量重要。


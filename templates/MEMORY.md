# Claude Code 自动记忆

## 行为规则（每次对话必读）
- **主动记忆**: 发现新知识、踩坑经验时立即写入对应记忆文件
- **去重更新**: 写入前先读目标文件，过时信息直接更新或删除
- **效率导向**: 记忆的唯一目的是减少重复解释
- **EverMemOS**: 重要技术决策也存入 EverMemOS（memory_store / soul_store）

## 记忆架构
- **MEMORY.md 文件系统**（主力）: 零延迟，每次自动加载
- **EverMemOS**（辅助）: 长期语义搜索

## 记忆文件索引
| 文件 | 内容 |
|------|------|
| `MEMORY.md` | 核心规则 + 索引（本文件）|
| `projects.md` | 各项目当前状态、架构、待办 |
| `preferences.md` | 用户偏好、习惯 |

## 用户
- __USER_NAME__
- 中文交流

## 关键教训
- **MCP 工具并行调用 bug**: Claude Code 用 Promise.all 调度并行工具，一个失败全批取消。不要把 MCP 工具和 Read/Bash 放同一批并行
- **macOS localhost 优先 IPv6**: 用 127.0.0.1

## 时间铁律
- 需要当前时间时 **必须 `date` 命令**，不要信系统提示的 currentDate

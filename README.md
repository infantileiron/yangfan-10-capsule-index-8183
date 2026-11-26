# 转町游艺 · 胶囊玩具出货盘试转点检

比较同口径试转数据，按偏离程度交接需要人工复检的机台。

模拟团队为 转町游艺机台整备点，6 人轮值，每周点检两种口径的胶囊玩具机约 80 台。。整备员在计量工位用标准空胶囊做 20 次出货循环，抄下出货间隔、定位偏差、转盘电流、壳体振动与重复推送数，再凭经验给机台排复检顺序。

- 两档胶囊口径对转盘阻力和间隔的影响不同，混用工位经验阈值会误判。
- 各项读数单看接近历史范围时，异常组合容易被交班员略过。
- 旧台账只留待复检机台号，下一班仍需逐页找测量偏移。

计量工位导出的 20 循环汇总表。近期历史没有故障标签，工位分出建模参照和留出读数。 复检员按队列到机台核对装配与量测记录，再走现行出货验收。导出表只用于人工点检交班。

## 业务模块

| 模块 | 工作内容 | 核心实体 |
|---|---|---|
| 二十循环测量单 | CSV 校验、预览实测字段、以完整数据内容的 SHA-256 去重、追溯版本和下载原始数据 | 数据版本 |
| 试转偏离筛查 | 按版本与领域参数创建计算单，由独立进程计算；从排队、成功或失败状态追溯 | 计算单 |
| 机台复检队列 | 按业务字段查看度量、比较与排序，下载计算结果 | 计算单及其结果 |
| 计量工位交接 | 对结果样本作签发或暂缓，记录理由，导出选中样本并查看审计时间线 | 交接记录 |

## 算法及口径

**Isolation Forest · 同口径留出阈值 · 参照偏移**。按胶囊口径分别用无故障标签的近期参照拟合隔离森林，原始异常度为 -100 × score_samples。以同口径留出段估算尾部复检线，按异常度减复检线的差值排序。单项证据用参照中位数和四分位距计算，显示偏移最大的两个实测值、参照典型值与单位。此偏移描述测量差异，复检员仍需确认原因。同口径试转需至少 30 条参照与 12 条留出，缺少待检、重复编号、量测超范围或参照全无变化时应修正计量单。

录入参数 **复检线分位**，默认 0.93，允许范围 0.8–0.99。同口径留出异常度的经验分位。提高分位会缩短优先复检名单。

演示集 `ZM-1125-出货盘二十循环读数.csv` 由 `backend/src/business/demo.py` 用固定数据或固定随机种子生成。工作台保留每次运行使用的输入版本、参数、结果和签审人。业务判断由服务端执行，前端图表直接读取返回的数值。

## 一天的工作剧本

1. 08:20 导入 ZM-1125-出货盘二十循环读数.csv，核对 48 和 65 mm 两档参照与留出记录。
2. 08:35 在本班试转组查 ZM-TR65-04，确认机台 ZM-B17 前后做满 20 个计量循环。
3. 08:55 以工程师账号运行筛查，将同口径复检线设在留出异常度第 93 百分位。
4. 09:00 在复检队列核对 ZM-TR65-04，电流中位值 1.86 A，优先检查出货盘传动。
5. 09:05 对照 ZM-TR48-01，确认 48 mm 工位中的近中位读数安排例行抽检。
6. 09:15 导出计量交班 CSV，按超线分差交接待复检机台和对应偏移明细。
7. 10:20 复检员现场重做 ZM-B17 的 20 个循环并回填机台日检表。

## 快速启动

```sh
test -f .env || cp .env.example .env
docker compose config --quiet
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```

前端在 `http://127.0.0.1:18329`，API 文档在 `http://127.0.0.1:19329/docs`，数据库绑定 `127.0.0.1:17829`。重复运行种子命令保留已有账号和版本。测试验收后用 `docker compose down` 停机可保留数据卷。重置本地演示数据可用 `docker compose down -v --remove-orphans`。

| 角色 | 登录邮箱 | 权限 |
|---|---|---|
| 分析员 | analyst@demo.local | 导入数据、提交计算、查看及导出 |
| 复核员 | reviewer@demo.local | 查看及导出、选择样本、签发或暂缓 |
| 观察员 | viewer@demo.local | 查看及导出已有内容 |

三个演示角色密码均为 `Yangfan-demo-2026`。Compose 默认绑定回环地址。自备数据可关闭 `SEED_DEMO`，并为需登录的环境另配账号和密钥。

## 技术与配置

| 服务 | 技术与职责 |
|---|---|
| frontend | HTML/CSS/JS ES 模块，Nginx 静态页面与同源 API |
| backend | Python 3.11、FastAPI、SQLAlchemy、JWT |
| worker | Python 后台进程，使用 DB 的原子认领、租约与重试，输出 CSV |
| db | MySQL 8.0，存账号、版本、计算单和审计 |
| redis | Redis 7，通知 worker 尽快拾取，任务状态由数据库持久化 |

`FRONTEND_PORT`、`BACKEND_PORT`、`DB_PORT` 管理回环端口，`JWT_SECRET` 为签名密钥，`DB_PASSWORD` 为应用数据库口令，`DB_ROOT_PASSWORD` 为数据库 root 口令，`COMPOSE_PROJECT_NAME` 控制该栈的命名空间。

本地 Python 开发可用 `docker compose up -d db` 启动关系库，并另起一个仅绑定回环的 Redis。Compose 内的 Redis 通过容器网络连接。用 Python 3.11 安装 `backend/requirements.txt` 后，进入 backend 目录，设置 `DATABASE_URL`、`REDIS_URL`、`JWT_SECRET`、`ARTIFACTS_DIR`、`SEED_DEMO`，分别运行 `uvicorn src.main:app --reload`、`python -m src.worker`。ARTIFACTS_DIR 需已存在且由两进程共享。前端可使用 Compose Nginx 镜像并重建以加载修改，或用已有 Nginx 反向代理本地 Python 端口。

`backend/src/business/` 保存本题字段、生成器和算法，`backend/src/services/` 处理资源生命周期，`backend/migrations/` 是初始关系模式，`frontend/src/` 按页面、API、会话、组件、路由及样式组织。前后端枚举分别在 `backend/src/constants/workflow.py` 和 `frontend/src/constants/enums.js`。角色用于 JWT 路由与表单权限，计算状态用于队列与结果页，签审决定用于交接页、审计和签发导出。

## 许可证

批次交付保留原作者权利。单独使用与再分发条款由项目所有者确定。

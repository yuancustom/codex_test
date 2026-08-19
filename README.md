# DXF Sheet Explorer

面向建筑施工图的 DXF 图框识别、拆图和 Web CAD 浏览器原型。

## 已验证样例

当前样例 DXF 已真实解析：

- DXF 版本：`AC1032`
- 原始文件大小：`41,415,351 bytes`
- 原始文件 SHA-256：`52986d56d094ad7807c958d3d3411cbdf838f62f17ed6a626c8ba88a99bab38d`
- 标准图框：`27`
- 施工图目录：`1`
- 正式施工图：`J01`–`J26`，共 `26` 张
- 未归入图框的模型空间实体：`2`
- 26 张拆分 DXF 已全部重新打开校验通过
- 拆分文件合计约 `45.3 MB`
- J01 顶层实体：`647`
- J01 展开块、标注和曲线后的 Web 可视实体：`1,474`

`data/manifest.json` 已包含 26 张图纸的图号、图名、图框坐标、实体数量和拆分文件名。

## 目录

```text
backend/                 FastAPI API
data/manifest.json       26 张图纸清单
data/source/             原始 DXF
data/sheets/             拆分后的 J01-J26 DXF
frontend/                React + TypeScript + Vite
tools/split_dxf.py       图框识别与拆图
tools/prepare_source.py  从 .gz/.xz 存档恢复原始 DXF
```

## 最简单的使用方式：网页上传

启动前后端后，左侧 `SOURCE DXF` 面板可以直接：

1. 选择 `.dxf` 文件并上传；
2. 后端流式保存并用 `ezdxf` 验证文件；
3. 点击“识别图框并拆分”；
4. 拆图在后台任务中执行，前端轮询显示 `0/26 ... 26/26`；
5. 完成后自动刷新 J01-J26 图纸目录。

上传限制为 100 MB。当前 41.4 MB 样例已经通过真实上传接口验证，返回文件大小和 SHA-256 与原文件一致。

## 数据准备（命令行方式）

原始文件路径：

```text
data/source/original.dxf
```

如果保存的是压缩存档，可先恢复并校验：

```bash
python tools/prepare_source.py data/source/original.dxf.gz \
  --sha256 52986d56d094ad7807c958d3d3411cbdf838f62f17ed6a626c8ba88a99bab38d
```

然后拆分 26 张图纸：

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
python tools/split_dxf.py data/source/original.dxf
```

## 后端

```bash
uvicorn backend.app.main:app --reload --port 8000
```

API：

- `GET /api/health`
- `GET /api/source`
- `POST /api/source/upload`
- `POST /api/source/split`
- `GET /api/source/split-status`
- `GET /api/sheets`
- `GET /api/sheets/{sheet_no}`
- `GET /api/sheets/{sheet_no}/entities?expand_blocks=true&limit=50000`

实体接口支持 LINE、POLYLINE、LWPOLYLINE、CIRCLE、ARC、TEXT、MTEXT、POINT、SOLID，并将 SPLINE/ELLIPSE 离散为曲线折线；INSERT/DIMENSION/LEADER 可展开为虚拟图元。

## 前端

```bash
cd frontend
npm install
npm run dev
```

打开 `http://localhost:5173`。Vite 会将 `/api` 代理到 FastAPI。

当前交互：

- 浏览器选择/上传 DXF
- 后台拆图任务与实时进度
- J01-J26 图纸切换
- CAD 图元 SVG 渲染
- 鼠标滚轮缩放
- 左键拖拽平移
- FIT 适配窗口
- 图层显隐 / 全部 / 清空
- 点击实体高亮并查看属性
- ARC 与曲线渲染
- 块、标注展开后渲染

## Docker

```bash
docker compose up --build
```

前端：`http://localhost:5173`  
后端：`http://localhost:8000`

## 测试

```bash
pip install -r backend/requirements-dev.txt
PYTHONPATH=. pytest -q backend/tests
```

当前本地回归测试：`6 passed`。真实样例已验证 26/26 拆分成功，26 个输出 DXF 全部可由 `ezdxf.readfile()` 重新打开。

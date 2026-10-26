# 雨崩 · 尼农线：徒步地形模型

这份项目用 `data/route.kml` 的 2,970 个轨迹点与真实 Copernicus GLO-30 高程数据生成实体模型。没有使用虚构山形，也没有上传个人轨迹到外部建模服务。浏览器依赖已下载到本地，预览无需外部 CDN。

## 查看

双击 `start_preview.command`，上传入口为 http://127.0.0.1:8765/ ，雨崩示例为 http://127.0.0.1:8765/web/ 。拖动旋转、滚轮缩放、右键平移；页面提供透视、北向上俯视、自动旋转和网格按钮。若服务已经运行，直接访问网址即可；终端提示端口占用时无需再启动。

## 打印文件

- `models/yubeng_ninong_print.stl`：首选打印几何，单一封闭实体，路线已凸起并与地形连续连接。STL 按毫米导入；格式本身不携带单位及颜色。
- `models/yubeng_ninong_color.3mf`：相同几何，毫米单位，当前默认含地形、水体蓝、林区深绿、冰雪白、路线红、草地、房屋白墙、图钉粉顶与深灰海拔刻度九种面材质。不同切片软件可能忽略面材质；这不是特定品牌打印机的工程文件。需要时自行分配颜色，或单色打印后涂路线。
- `models/validation.json`：参数、尺寸和几何验证结果。
- `web/preview.png`：第一版浏览器截图（保留）。
- `web/preview-features.png`：地表要素版默认透视截图，已由外部无头 Chrome 生成并由用户确认渲染正常；早于本次照片叠加。

尺寸约 200 × 132.2 × 76.0 mm（含南侧 0.35 mm 浅浮雕，原地形 XY 为 200 × 131.9 mm），底面平整，雕刻前最低厚度 4 mm；水槽下压后最薄处约 3.55 mm。水平比例约 1:47,985，垂直夸张 1.25 倍。覆盖约 9.6 × 6.3 km。路线基底宽约 1.7 mm，凸起最高 0.8 mm，边缘渐变，受 0.32 mm 网格采样影响会有离散误差。

推荐作为首次试打起点：FDM / PLA / 0.4 mm 喷嘴 / 0.16–0.20 mm 层高 / 3 道墙 / 10–15% 填充，平底朝下。山体是单值高度场，通常不需要支撑；仍需在所用设备的切片软件中检查实际预览、尺寸、薄壁和耗材。没有执行真实打印，也没有在本机安装切片器或生成特定机器 G-code。JSON 中约 881 cm³ 是实体几何体积，不是稀疏填充的实际耗材量。

## 数据与精度

原轨迹：2026-09-17，两步路 KML，记录起点“雨崩景区南门”、终点“神瀑客栈”。原文件记录 14.456 km；按导出坐标逐段测地线重算约 14.220 km，两者算法与采样口径不同，界面采用原文件记录值。

按照标准 KML 将坐标解释为 WGS84，经 EPSG:32647（UTM 47N）投影计算；不对其进行未经确认的 GCJ 偏移。记录海拔减去 DEM 的中位差约 -1 m，绝对差第 90 百分位约 17 m，支持地形匹配，但不能代替外业定位精度检验。模型路线高度从 DEM 重新采样，避免手机海拔噪声导致路线悬空。

高程来自 Copernicus DEM GLO-30（DSM，约 30 m），重采样不会增加真实细节。表现的是周边山脊与山谷，不包含真实单体树木、房屋、步道台阶或卫星影像颜色。地表类别由下述公开数据决定，颜色是分类展示配色，不是卫星影像颜色。

数据集介绍：https://registry.opendata.aws/copernicus-dem/
官方说明及许可入口：https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM
实际数据：https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N28_00_E098_00_DEM/Copernicus_DSM_COG_10_N28_00_E098_00_DEM.tif

Attribution: © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018. Provided under COPERNICUS by the European Union and ESA; all rights reserved.

## 重新生成

项目已有隔离的 `.venv`，执行：

```sh
cd /Users/huan/Desktop/workspace/huan/huan-path
.venv/bin/python build_model.py
```

`build_model.py` 包含数据裁剪、投影、轨迹加密、浮雕生成、封边封底、STL/3MF 导出和 STL 回读验证。`data/terrain_crop.tif` 是本次使用的投影高程裁剪。`requirements.txt` 记录依赖版本。预览与打印文件使用同一套顶点及三角形，配色除外。

## KMZ 输入（已验证）

同样支持 KMZ，直接在压缩包内读取 `doc.kml`，无需手动解压，也不会将包内附件解压到文件系统：

```sh
.venv/bin/python build_model.py data/route.kmz
# 或使用原始文件的绝对路径
.venv/bin/python build_model.py /Users/huan/Desktop/paths/2026-09-17-yubeng.kmz
```

2026-10-21 检查的 KMZ 仅包含 `doc.kml`，其内容与前一次使用的 KML 逐字节相同，均为 2,970 个轨迹点。因此用这份 KMZ 生成的地形与路线保持一致。KMZ 中可能存在的照片或图标不作为三维地形数据。当前原型读取 gx:Track 格式轨迹，并使用项目内已下载的雨崩 DEM；它还不是适配任意地区的通用转换器。


## 河流、湖泊、树林、草地与冰雪（2026-10-21 更新）

### 原始数据与许可

所有要素投影到 EPSG:32647 后裁剪到原模型的相同边界（不扩大模型）。UTM 边界为 `[478683.989676, 3135247.047409, 488281.089584, 3141576.027945]` 米。

1. **OpenStreetMap / Overpass**：`data/osm_features_raw.json` 是完整原始 JSON 响应，`data/osm_query.overpassql` 保存查询，`data/osm_source.json` 保存成功接口、OSM 数据时间戳、下载日期、哈希和请求失败记录。查询 `waterway=river/stream`、`natural=water`，以及 `landuse=forest`、`natural=wood/glacier`。成功接口为 `https://overpass-api.de/api/interpreter`，GET 请求带明确 User-Agent。先前 POST/TLS 失败及另一实例限流/超时没有被当作空数据。数据许可 **ODbL 1.0**，署名 **© OpenStreetMap contributors**。许可及署名说明：https://www.openstreetmap.org/copyright 。原始及裁剪后的 OSM 数据分发仍适用 ODbL；`data/osm_features_utm47n.geojson` 为裁剪派生数据，坐标为 UTM 米，不是常见 GeoJSON 经纬度。
2. **ESA WorldCover 10 m 2021 v200**：`data/worldcover_2021_N27E096.tif` 保存下载的原始 3°×3°瓦片，`data/worldcover_crop.tif` 保存模型网格上的最近邻重采样分类；`data/worldcover_source.json` 保存 URL、版本、哈希与许可。原始 URL： https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N27E096_Map.tif 。使用分类 10（树木覆盖）、30（草地）、70（雪和冰），OSM 林地与冰川面作为补充。许可 **CC BY 4.0**：https://creativecommons.org/licenses/by/4.0/ 。说明：https://esa-worldcover.org/en/data-access ，数据引用：Zanaga et al. (2022), ESA WorldCover 10 m 2021 v200, https://doi.org/10.5281/zenodo.7254221 。署名：**© ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium**。
3. 山体仍使用前述 **Copernicus GLO-30**。分类数据为 10 m 不意味着山体精度提高到 10 m。

### 本范围实际取得的要素

Overpass 原始响应共 16 个要素。精确裁剪后保留 2 条 river way、6 条 stream way、2 个河流面、1 个湖泊、2 个林地面和 1 个冰川面；它们是 OSM 分段对象数量，不等于独立河流数量。包含澜沧江、巴些隆曲（雨崩河）、雨崩隆曲及神湖。部分要素只在边界处进入很小的面积。原始关系的内外环会组装并保留岛洞。

WorldCover 原始分类在模型网格上约有 156,496 个树木像元、78,024 个草地像元和 **58 个冰雪像元**。这是重采样后的模型网格统计，不是 10 m 原始像元数量，也不是树木棵数。加入 OSM 并处理覆盖优先级后，林区掩膜为 160,474 个网格顶点，冰雪为 63 个顶点；神湖只有 8 个网格顶点，因此湖泊与冰雪在总览图中都很小。本次所需数据类别均有有效数据，没有按海拔猜测或扩张雪线，也没有虚构水系和树的位置。

### 几何与材质

- 河流/溪流沿 DEM 下压 **0.45 mm**。为可打印、可见，河流槽宽符号化为 **1.4 mm**、溪流为 **1.1 mm**；这不是测得的真实宽度。OSM 河流面也下压，但仍保留沿程坡度。
- 湖泊面（排除岛洞）按局部 DEM 中位高度再下压 0.45 mm，生成同一水平面的湖面。真实水位未被测量，整平所需的局部高差可能大于 0.45 mm。当前湖面高度约 67.890 mm（模型坐标）；红色路线若与湖相交，路线仍凸起，湖面平整检查会排除路线。
- 林区抬高 **0.321–0.439 mm**，高于 0.2 mm 层高；轻微纹理是固定、可重复的程序纹理，只表示林区表面，不是单体树或真实树冠。纹理自身峰谷小于一层，整体林区台阶大于一层。
- 草地只使用浅绿色材质；冰雪/冰川只使用白色材质，不改变高程。
- 红色路线在房屋空隙之外最后处理，比原地形和已修改地表中较高者再高 **0.8 mm**；启用的 true 房屋空隙内不凸起、不着红色，见下文。
- 全部仍是一个高度场封闭实体，底面 z=0 平整。无独立树模型、悬空河面或额外外壳。STL 不带颜色但保留水槽、林区凸起及路线；3MF 中六类分别是面材质。预览直接读取与打印文件相同的几何及面材质 ID，类别边界不进行颜色混合。

`models/validation.json` 记录各类数据数量、面材质数量、槽深、林区高度、湖面水平验证、冰雪几何零变化、路线净高、最薄处厚度，以及 STL/3MF 回读封闭性、单一连通体和 Manifold 检查结果。没有执行设备切片和实际试打，面材质在不同切片软件中仍可能被忽略。

### 精度和时效局限

WorldCover 是 **2021 年分类**，不代表 2026 年 9 月徒步当天的积雪、植被或水位；分类错误及山地阴影误判都可能存在。OSM 是志愿者数据，水系与林地边界可能缺失或与 30 m DSM 不完全对齐。林区使用 WorldCover 树木覆盖与 OSM 林地并集，可能与草地分类存在冲突；优先级为路线 > 水体 > 冰雪 > 林区 > 草地 > 地形。未将 WorldCover 的水体分类自动转成湖泊，避免把河道误作水平湖面。模型网格仍约 0.32 mm（地面约 15 m），小斑块可能丢失或仅占数个三角面，无法呈现真实 10 m 边界细节。

重新生成仍执行 `.venv/bin/python build_model.py data/route.kmz`；数据获取与建模分开，已有原始数据时建模不需要访问远程 API。


### 浏览器验证状态与补齐方法

**历史记录：上一轮代理内浏览器验证受限；现已由用户确认外部无头 Chrome 渲染正常，并提供 `web/preview-features.png`。** 以下保留当时的限制与复现方法；该截图不是本次照片交互版的新截图。 浏览器控制工具返回 Chrome/Safari 未获准操作；随后用项目内独立安装的 Chromium（包括 headless shell）尝试离屏测试，进程仍被当前代理沙箱阻止，报错为 `MachPortRendezvousServer / bootstrap_check_in: Permission denied (1100)`。没有用其他渲染图冒充浏览器截图。记录在 `work/browser-validation.json`，日志在 `work/browser-error.log`。

已经完成 JavaScript 语法检查、网页与本地资源 HTTP 可达性检查，以及预览顶点/三角面/材质 ID 与 3MF 的一致性检查。这些检查不能代替实际 WebGL 渲染。

项目包含隔离的 Playwright 测试浏览器与验证脚本。可在**普通本机终端（不受代理沙箱限制）**执行：

```sh
cd /Users/huan/Desktop/workspace/huan/huan-path
# 先启动预览服务（如果已在运行则不用重复启动）
# .venv/bin/python -m http.server 8765 --bind 127.0.0.1
./verify_preview.command
```

成功时会检查 WebGL 加载、六类图例、页面错误和资源请求，保存默认透视截图至 `web/preview-features.png`，保存俯视/窄屏截图至 `work/`，并把 `validation.json` 与 `metadata.json` 的 `browser_validation` 更新为 passed。新建模后应再次执行验证，避免使用旧截图代表新几何。


## 两步路照片标注（2026-01-27，网页预览专用）

### 来源与文件

这 28 个照片点来自另一次 **2026-01-27「尼龙进村」** 徒步，不是模型红线所代表的 **2026-09-17** 轨迹。两次徒步与 WorldCover 分类的时间不同，照片中的植被、雪况和模型配色不一定一致。

只读源文件保持原位且 SHA-256 核对未改变：

- `/Users/huan/Desktop/paths/2026-01-27-yubeng.kmz`
- `/Users/huan/Desktop/paths/2026-01-27-yubeng.kml`

`data/photos-2026-01-27/` 保存源 KMZ 副本 `source.kmz`、在线链接版 KML 副本 `source-online.kml`、KMZ 内原始 `doc.kml`、`originals/pic_<FileId>.png` 原照片和 `manifest.json`。导入只选择「标注点」文件夹中的 `MarkerStylePicture`，以 ExtendedData 的 FileId 对应 `files/pic_<FileId>.png`，28/28 匹配成功；在线 KML 中相同 FileId 的坐标也已逐一核对一致。原始 `.png` 附件实际为 JPEG 编码，备份保持原字节和文件名，不做修改。

网页使用 `web/photos/<FileId>.jpg`（EXIF 方向校正，长边不超过 1200 px，不放大小图）与 `web/photos/thumbs/<FileId>.jpg`（长边不超过 240 px），不读取两步路在线图片，也不上传照片。`web/photos/points.json` 为网页点位与图片映射，`web/metadata.json` 的 photos 节保存来源、数量和范围检查结果。照片是用户提供内容，未推定其具有公开再分发许可。

### 坐标、高度与范围

使用原模型的 WGS84 → EPSG:32647、相同 UTM 原点、水平比例与 1.25 倍高度夸张。28 个点全部位于当前模型矩形范围内，**范围外 0 个**，未移动或吸附点位到红色路线。若以后有范围外点，会记录在 `photos.out_of_bounds` 并出现在照片列表中，但不创建范围外 3D 标记。

海拔在现有 `data/terrain_crop.tif` 上双线性采样，模型锚点高度按 `4 + (DEM海拔 - 模型最低海拔) × 水平缩放 × 1.25` 计算。原始记录海拔仅留在数据中，不用于摆放，也不作为弹窗主海拔。为了不被林区凸起或红线遮住，标记符号抬到 DEM 锚点与网页已生成表面二者较高处之上 2.2 mm，并以细杆连回 DEM 锚点。这是网页交互符号偏移，不是测得的照片海拔。

### 使用

- 默认显示醒目的黄色编号照片点；「照片点」按钮可整体开关。
- 悬停标记显示标注时间与 DEM 海拔；点击打开本地大图、时间、海拔、经纬度与 FileId。
- 「照片列表 (28)」提供缩略图选择，可访问位置接近、重叠或被山体遮挡的照片。
- 大图支持上一张/下一张、左右方向键、关闭按钮和 Esc。时间统一为北京时间（Asia/Shanghai，UTC+8）。

原始名称与文字备注为空，因此只生成「照片 01」等编号，不编写照片内容描述。界面中的拍摄时间来自 KML ExtendedData `Time` 毫秒时间戳，**未与照片 EXIF 拍摄时间核验**，可能是标注或上传记录时间；记录范围为 2026-01-27 11:29:55–15:45:53。DEM 为约 30 m 高程数据，地理配准、坡地插值和定位误差都可能影响标记位置。

### 验证与重新导入

执行 `.venv/bin/python import_photos.py` 可重新导入这一份源数据。重建地形后也应重新导入，以更新 DEM 锚点和网页表面高度。`build_model.py` 会保留照片来源摘要，不把照片编号标记写进打印网格；当前房屋符号按后文单独控制。

本次 STL/3MF、地形二进制与地表面材质均不因照片叠加而改变；已核对 STL/3MF SHA-256 一致。28 对网页图片和缩略图均可解码、HTTP 200，来源文件校验一致。`work/photo-ui-validation.json` 记录 DOM 与真实 Three.js 数学/场景交互测试（28 标记、开关、列表、大图、前后导航、射线悬停与点击、DEM 锚点），这些是无 WebGL 的集成检查，不冒充新版本的真实浏览器渲染验证。上一轮外部截图仍原样保留。

## 统一元素配置与照片房屋识别（当前版本）

### 配置与重建

统一配置为 **`config/features.json`**。`rivers`（河流、溪流、湖泊）、`forest`（林区）、`grass`（草地）、`snow`（冰雪）、`houses`（房屋）、`photos`（照片叠加）分别有 `enabled`。默认全部开启，房屋 `include_uncertain: false`。红色徒步路线与地形底座始终保留，不属于可移除元素。

```sh
cd /Users/huan/Desktop/workspace/huan/huan-path
# 使用配置生成最终 STL、3MF、网页几何与 metadata
.venv/bin/python build_model.py
# 临时去掉水系与林区，不修改配置文件
.venv/bin/python build_model.py --disable rivers,forest
# 临时去掉房屋或照片；二者互相独立
.venv/bin/python build_model.py --disable houses,photos
# 可读取另一份配置，或临时开启配置中关闭的元素
.venv/bin/python build_model.py --config config/features.json --enable forest
```

长期关闭元素：把对应 `enabled` 改为 `false` 并重建。`--disable` / `--enable` 接受逗号分隔名称；同名同时出现时 `--enable` 最后生效。未知名称或不合理参数会报错，避免静默忽略。

参数包括水槽深度/河溪符号宽度、林区凸起/纹理幅度、房屋宽度/墙高/屋顶高及 uncertain 是否纳入。为了保持当前打印尺度，水槽深度约束在 0.3–0.6 mm；林区整体凸起大于 0.2 mm、上限 0.5 mm；房屋宽 2–3 mm。可用 `--output-dir work/my-test` 把试验产物隔离输出至其 `models/` 与 `web/`，不替换主模型。

关闭元素会从打印高度场与面配色中移除：例如关水系恢复原始 DEM，不保留蓝色槽底；关林区恢复原高度、普通地形色；草地/冰雪本来只有配色，关闭时恢复普通地形色。源分类优先级固定，关闭上层类别不会凭空把它猜成另一类地表。房屋移除后露出其下仍开启的地表。3MF 只写入当前实际使用的面材质；关闭的浮雕层不会写进活动网页高度图层文件。原始数据和照片附件保留，方便以后恢复。

`photos.enabled` 仅控制网页是否加载照片图层与列表，不参与 STL/3MF 计算。房屋从人工识别表独立生成，关闭照片不会顺带去掉房屋。

### 网页即时开关

预览增加水系、林区、草地、冰雪、房屋开关，原有照片点开关继续保留。切换后会重算顶点高度、法线与面配色，图例同步变化，不是删除三角面或制造空洞。房屋显示为棕色坡屋顶小块，与打印模型一致。照片符号会随地表变化重新抬高，仍连接到 DEM 锚点。

**网页开关只影响当前显示，下载按钮仍指向最近一次构建的文件。要改变打印内容，必须改配置或命令行参数并重新构建。** 被构建配置关闭的元素，网页按钮显示“未构建”且禁用；想重新显示需先启用并重建，因为该次活动网页数据已经不含它。刷新页面恢复最近构建的配置，不把临时显示状态写回磁盘。

### 房屋判断：人工可编辑

已逐张实际查看 28 张原始照片，判断保存为 **`data/photo_houses.json`**（不会因重建或重新导入照片而覆盖）。每行有照片编号 `photo_index`、FileId、经纬度、`has_house`、简短理由及查看的原图路径。初始结果：

- **true：7、12、20、23、25，共 5 个点。** 分别可见坡地小屋、近处白墙建筑、坡地多层建筑、近处在建楼房/村舍、村落与白塔等。
- **uncertain：1、18、19，共 3 个点。** 远处疑似村舍/棚屋，因距离与遮挡不能可靠确认，默认不放。
- false：其余 20 个点。仅见峡谷、桥梁、设备、树木、动物或步道等，没有可确认房屋；桥梁、标牌和太阳能监控杆不当作房屋。

把某行 `has_house` 改为 JSON `true` 即可增加该点房屋，改为 `false` 即可去掉。`"uncertain"` 是字符串，若想纳入这类点，将配置 `houses.include_uncertain` 改为 `true`，然后重建。也可修改坐标或增加不同编号的记录，修改理由帮助以后复核。已有初始判断是看图结论，不是自动建筑测绘，可能误判；保留原图便于人工修正。

**照片点是拍摄者所在位置，不是被拍房屋的实际位置。模型不推测朝向或偏移，直接在记录坐标放一个符号房屋。** 同一建筑可能被不同照片重复拍到，因此这里的 5 个点不等于 5 栋真实建筑；相近符号可能重叠、合并，不自动去重或移动。2026-01-27 照片也不证明建筑在 2026-09-17 的状态。

默认房屋约 2.6 mm 见方，墙高 1.2 mm、坡屋顶高 0.6 mm。墙基以局部 DEM 较高处作为支撑，在陡坡上会有更高的符号化基础；不代表真实房屋尺寸或地基。房屋通过修改连续高度场生成，整体填实，与山体直接相连，无独立壳体或内部悬空面。红色路线在 true 房屋周围按 route_gap_mm 断开，其余区域最后凸起 0.8 mm。关闭房屋恢复完整路线。

### 配置组合校验

`feature_engine.py` 统一实现配置校验和高度合成；网页 `web/features.js` 用同样顺序即时合成。32 种地形元素组合（再乘不影响几何的照片开关，共 64 种）在固定网格拓扑下检查封闭性、面朝向、正体积、平底、最小厚度和路线净高；Python 与网页高度最大差约 0.000004 mm。记录在 `work/combination-check/results.json`、`work/feature-ui-validation.json`。另实际导出验证 `--disable rivers,forest` 后无相应几何层及 3MF 材质，并验证纳入 uncertain 后可生成 8 个房屋点、同时关闭照片图层。最终交付恢复默认全开启并进行 STL/3MF 回读与 Manifold 检查。当前截图仍由外部完成，代理没有启动浏览器。

前文“照片叠加不修改打印文件”仍适用于照片图层本身；**本轮新增且默认开启的房屋浮雕会有意修改 STL/3MF 几何**，不应再拿先前照片导入时的哈希要求当前房屋版一致。所有历史截图仅对应其生成时版本，不能作为当前配置的截图。


### 本轮默认导出变化

相对未加入房屋的上一版，外形尺寸仍约 **200 × 131.894 × 76.024 mm**，网格仍是 **261,241 顶点 / 522,478 三角面**（房屋通过修改顶点高度加入，而不是拼接独立网格）。实体体积由 **880.635864 cm³ → 880.728179 cm³**，增加约 **0.092316 cm³**；这不是实际打印耗材估算。3MF 实际面材质由 **6 类增加至 7 类**，新增房屋棕。STL/3MF 均重新导出并通过封闭、单连通实体、底面 z=0、朝向一致及 Manifold 检查，路线在房屋空隙外位于局部地表之上；房屋空隙内不生成路线。前后变化也记录在 metadata/validation 的 `change_from_feature_only`。


## 房屋周围的路线空隙（当前规则）

`config/features.json` → `houses.route_gap_mm` 控制模型毫米单位的圆形空隙半径，默认 **2.1 mm**（2.6 mm 房屋半宽 1.3 + 0.8）。半径从照片/房屋点的 XY 坐标量起，打印和网页使用相同规则。只对**启用房屋且 has_house 为 JSON true** 的点留空隙；`false`、`"uncertain"` 不创建空隙，即使 include_uncertain 开启也不额外给 uncertain 房屋断路线。多个 true 圆形空隙取并集。

空隙内直接使用“房屋 + 仍启用的地表”，不抬高路线、不分配红色材质；空隙外路线照旧。与空隙顶点相接的三角面也取消红色，避免红色在离散网格边缘染上屋顶，因此颜色断口在网格边缘可能略宽约一格（0.32 mm）。房屋关闭时，不再应用顶点/三角面空隙掩膜，完整恢复路线几何与红色。网页的房屋开关也即时执行同样的恢复，不需要重新加载页面；改变下载文件仍需重建。

`houses.preview_color` 默认 `#FFAE58`，网页房屋显示为更醒目的橙色，打印尺寸和 3MF 房屋棕色材质不因这一网页颜色参数而改变。截图时若照片编号符号遮住房屋，可先关“照片点”。

默认配置下，每个圆内原始路线中心线的水平长度如下（按路线原始折线逐段解析求交，不包括路线条带宽度，不是三维累计步行距离；重复经过计入，圆之间若重叠不能简单相加）：

| 房屋/照片编号 | 模型内路线长度 mm | 对应地面水平长度 m |
| --- | ---: | ---: |
| 7 | 3.8875 | 186.54 |
| 12 | 7.1554 | 343.36 |
| 20 | 5.7537 | 276.09 |
| 23 | 3.3704 | 161.73 |
| 25 | 0.5350 | 25.67 |

这些长度统计的是 2026-09-17 路线与 2026-01-27 房屋标注圆的交集，两个日期不同。实际渲染条带边界会受路线宽度和网格采样影响。参数改变后应以 metadata/validation 中 `houses.placed_points[].route_gap_centerline_length_mm` / `_m` 的新计算值为准。长度为 0 代表中心线未进入该圆，并不代表程序虚构移动路线来经过房屋。

12 号房屋在当前 Three.js 场景中的屋顶中心大约为 **(134.22, 28.42, 16.52)**，单位 mm，Z 向上。其原始 DEM 锚点约为 (134.22, 28.42, 13.12)，符号化屋顶高于锚点；截图近景目标应看屋顶中心而非 DEM 点。`houses.placed_points[].scene_roof_center_mm` 保存实际生成屋顶中心的场景坐标。

新校验规则为：空隙顶点高度等于无路线的房屋/地表高度；空隙三角面无红色；空隙外红色核心高出局部地表 0.8 mm；关闭房屋后路线完整。另保留封闭、单一连通体、平底、面朝向与 Manifold 校验。旧版本“路线在房屋上方”的规则已由此替换。

## 当前房屋方案：地图图钉屋（替代旧高度场房屋）

当前使用用户提供的 `data/house_designs/5_pin_house.stl` / `.glb`，Z 向上、mm，原始约 3.40 × 3.40 × 3.95 mm。上述早期版本中“抬高地形顶点生成房屋”的说明已被本节替代。房屋位置仍来自 2026-01-27 拍摄点，并非建筑测绘位置；默认放置 7、12、20、23、25，`include_uncertain=true` 时也放置 uncertain 点，且同样断开其周边路线。

统一配置为 `config/features.json` 的 `houses`：

- `model_stl`、`model_glb`：设计文件路径。构建检查两者尺寸和体积相符；GLB 为分色来源，STL 为焊接拓扑来源。替换设计时应同时提供相同几何的文件。网页本地 GLB 读取器支持当前无纹理三角网格、节点变换与紧密排列的顶点数据；不支持压缩、纹理、交错 accessor，遇到不支持的布局会报错。
- `scale: 1.0`、`sink_mm: 0.4`：等比缩放，底面中心放在当前地表下 0.4 mm。地表不再因房屋抬高，仍保留原有林区/水体效果。陡坡可能遮住图钉的一部分；每栋均检查与地形有正体积交集。
- `route_gap_mm: 4.0`：以房屋中心为圆心的路线空隙半径。顶点额外扩展两格对角线，避免粗网格插值让凸起伸入空隙。凹凸和红色都移除，圈内恢复原地表。
- `min_route_clearance_mm: 0.0`：房屋投影边缘到任何凸起或红色路线三角面的最小水平净距要求。构建同时检查中心距离 ≥ `route_gap_mm`；默认实测边缘净距 2.876–5.756 mm。缩放后空隙半径必须至少为 `1.7 * scale + 1.5`；净距结合网格额外留白按实际三角面校验：房屋完整投影与任何凸起或红色路线三角面必须严格大于 0（不能接触或重叠），并满足配置的附加净距阈值。本轮按用户新要求将旧的 3.5 mm 校验阈值改为 0.0；这只改变校验门槛，不改变房屋造型或放置。
- `pin_color: "#F4A7B9"`：浅粉色，用于图钉、屋顶和门，与路线橙红 `#E94F39`、草地绿和冰雪白区分；白墙保持 `#F7F7F2`。源设计 GLB 不修改；构建导出的 `web/house_designs/5_pin_house.glb`、网页材质、图例“图钉粉顶”和 3MF 均使用配置粉色。
- `enabled: false` / `python build_model.py --disable houses`：无房屋、无路线空隙。`include_uncertain` 和 `list_file` 保持可用。启用点之间的空隙会取并集。

重建：`.venv/bin/python build_model.py`。只在网页切换“房屋”会隐藏/显示独立 GLB 实例并恢复/断开路线；切换林区和水体会重新贴合房屋高度。下载的打印文件仍以最近构建配置为准。

STL 使用 manifold 对地形和所有图钉屋做布尔合并，输出一个封闭实体；合并过程中仅填充封闭的负体积内部小空腔，不移除断开的正体积外壳，若有断开的外壳则构建失败。3MF 为同一合并表面，利用 manifold 面来源保留普通地形、水体、林区、草地、冰雪、路线以及白墙/图钉粉顶，共 8 种面材质。网页使用可切换的地形网格及独立 GLB，表面位置与打印放置一致，不将布尔结果硬编码为不可切换的网格。

默认重建后的房屋边缘到最近剩余路线的水平净距：7 号 2.876 mm、12 号 2.954 mm、20 号 2.964 mm、23 号 2.908 mm、25 号 5.756 mm。该距离计算使用房屋完整 XY 投影与所有凸起或红色路线三角面；包括被地形埋入部分的投影，因而对可见部分是保守净距。不是拍摄地真实建筑与步道的距离。

12 号网页房屋原点约 `(134.216, 28.420, 13.079)`，屋顶最高中心约 `(134.216, 28.420, 17.029)`，单位 mm、Z 向上。相邻照片点可能代表同一个村庄，当前仍按每个标注各放一个图钉，没有推断偏移或去重。

校验结果写入 `models/validation.json` 与 `web/metadata.json`。默认 STL/3MF 均通过序列化后的封闭、方向一致、单连通组件和平底检查，manifold 无错误。默认合并体 genus=1（有贯通孔道，仍是单一封闭实体）；不要求模型必须与球同拓扑。`work/pin-houses-off/` 保存关闭房屋的独立构建验证，网页 DOM/Three.js 检查为 `work/pin-ui-validation.json`，覆盖 GLB 材质、5 个实例、开关恢复路线和 32 个元素组合；这不是浏览器截图测试。本轮截图由外部完成。

房屋设计由用户提供；本项目未给它推定第三方许可。DEM、WorldCover、OSM 与原始照片来源/许可沿用前述记录，没有新增或编造地理数据。

本轮将路线空隙半径改为 4.0 mm，按严格正净距/不重叠规则校验；图钉/顶色保持浅粉 #F4A7B9；房屋缩放 1.0、下沉 0.4 mm 与陡坡布尔处理保持不变。当前默认导出和网页 GLB/材质检查均通过；未生成截图。


## 单侧海拔刻度（当前实现）

海拔刻度数据源现已改为主轨迹 `data/route.kml`（2026-09-17）首尾点记录海拔，**不是 DEM 全范围最低/最高，也不是轨迹全程最低/最高**。实际起点 2009.541496 m、终点 3064.796875 m；全程记录最低 2006.294914 m、最高 3080.896367 m，仅保存作参考，不用于本组刻度。

按首尾记录海拔等分三个区间、产生四条线。数字取整到米，几何高程使用未取整值，映射仍以模型 DEM 的最低海拔为零基准：

```text
alt_i = route_start_alt + i * (route_end_alt - route_start_alt) / intervals
z_i = base_mm + (alt_i - dem_min) * (1000 / horizontal_scale) * vertical_exaggeration
```

因此第一条不是简单放在底座 4 mm 上，也不会把起点记录海拔改成 DEM 采样的起点海拔；它表示 GPS 记录海拔在模型高程体系中的位置。

| 显示文字 | 真实记录/插值海拔 m | 模型 Z mm | 放置 |
| --- | --- | --- | --- |
| S 2010 m | 2009.541496 | 4.977939 | 原位，无下移 |
| 2361 m | 2361.293289 | 14.140910 | 原位，无下移 |
| 2713 m | 2713.045082 | 23.303881 | 原位，无下移 |
| E 3065 m | 3064.796875 | 32.466852 | 原位，无下移 |

全部原位显示，不存在 `4737 m*`，当前网页也没有星号/下移提示。`S` 表示起点、`E` 表示终点，避免毫米尺度中文笔画的打印风险；S/E 与数字同样采用 4.5 mm 高、0.6 mm 笔画的实体字。字母 m 是单位符号，首尾标记不会被误解成另两种海拔来源。

刻度仍只在**南侧壁**：默认视角可见、侧壁面积约 9109.651 mm²，为四面最大。刻线长 7.0 mm、宽 0.6 mm，深灰 `#39434B`，浅浮雕向外凸出 0.35 mm，向实体内搭接 0.15 mm。文字和线条在局部坐标生成后与侧壁限高薄层求交，并与地形、房屋布尔合并。字高/笔画/侧面/颜色、房屋与断口等其余参数不变。当前四项不需要截短或移位。

### 配置与切换

`config/features.json` 新增 `elevation_scale.source`，默认 `route_start_end`；`terrain_min_max` 保留 DEM 范围刻度能力，只有显式选择时才使用旧的 DEM 极值模式。该模式仍可能需要下移最高项，网页会按实际 relocated 状态显示说明，不会把旧提示无条件显示到首尾模式。

| 字段 | 当前值 | 含义 |
| --- | --- | --- |
| `elevation_scale.enabled` | true | 启用打印刻度与网页刻度层 |
| `elevation_scale.source` | `route_start_end` | 可选 `route_start_end` / `terrain_min_max`；缺省补为首尾模式 |
| `elevation_scale.side` | `south` | 支持 south / north / east / west，当前南侧 |
| `elevation_scale.intervals` | 3 | 整数 1–10，四条线为当前默认 |
| `elevation_scale.depth_mm` | 0.35 | 固定 emboss 模式的凸出量，范围 0.3–0.6 mm |
| `elevation_scale.line_width_mm` | 0.6 | 刻线宽，范围 0.5–2 mm |
| `elevation_scale.tick_length_mm` | 7.0 | 短线长度，范围 3–20 mm |
| `elevation_scale.text_height_mm` | 4.5 | 数字与 S/E 高度，范围 4–10 mm |
| `elevation_scale.stroke_mm` | 0.6 | 字体笔画，范围 0.5–1.2 mm |
| `elevation_scale.color` | `#39434B` | 网页/3MF 深灰材质 |

执行 `.venv/bin/python build_model.py` 重建；`.venv/bin/python build_model.py --disable elevation_scale` 移除打印刻度。网页“海拔刻度”按钮只切换显示，不能改写已下载打印文件。`elevation_scale.py` 生成独立的网页浮雕缓冲 `web/layers/elevation_scale_vertices.bin`（Float32 XYZ）与 `web/layers/elevation_scale_faces.bin`（Uint32 索引），原地形缓冲不改动。

### 元数据、校验与本次迭代

`metadata.json` / `validation.json` 的 `elevation_scale` 保存 source、source_endpoints_m、dem_mapping_range_m、route_recorded_min_max_m；每条刻度保存 role、elevation_m、label、nominal_z_mm、display_z_mm、relocated。当前四条 `relocated=false`，理论与显示 Z 相等。

本次修正顺序：最初以全 DEM 范围等分、最高项下移加星号 → 用户明确纪念对象应是徒步起终点 → 读取主轨迹首尾 GPS 海拔等分，增加 source 开关，首尾用 S/E，全部原位并移除默认星号说明。没有把全程最低/最高误作首尾值，也没有改变高程夸张、底座或地形。

STL/3MF 均通过回读封闭、绕序一致、单实体、平底和 Manifold `Error.NoError` 校验；当前仍为九种面材质。`work/check_elevation_scale.py` 验证主轨迹首尾等分、四条真实 Z、S/E 标签、无下移、浮雕单侧与底面范围及材质；`work/browser-test/check-pin-houses.mjs` 覆盖网页载入和开关。另以独立输出目录验证 `terrain_min_max` 仍可生成旧模式，不覆盖默认网页数据。未生成截图，也没有新的实物打印验收。

当前实体 262,401 顶点、524,802 三角面，尺寸 200.000000 × 132.243600 × 76.024284 mm，体积 880.702669 cm³。网页浮雕独立网格 652 顶点、1220 三角面。S/E 是记录海拔标签，GPS 与 DSM 垂直基准/误差差异仍保留，不能将此刻度当作精密高程量具。


## 上传与流水线（本地应用阶段）

现已新增本地上传应用：入口 `/`，示例作品保留 `/web/`。运行 `server.py` 替代只读 `http.server`，默认绑定 `127.0.0.1:8765`。浏览器无需 Node 打包即可使用。旧静态服务必须先停止，不能在同一端口同时运行两个服务。

### 启动与当前端口交接

```sh
# 在项目根目录执行；双击 start_preview.command 也可
.venv/bin/python server.py
# 若旧 http.server 仍占用端口，请在其原终端 Ctrl+C 后再启动。
# 需要并行保留旧示例服务时可临时使用其他端口：
.venv/bin/python server.py --port 8766
```

`start_preview.command` 会识别已经运行的应用服务；若尚未运行，启动默认 8765 并打开上传入口。该脚本不会强制终止未知进程。本轮验证时 8765 的旧静态服务由外部进程持有，沙箱终止该进程被系统拒绝，因此实际 HTTP 验收使用 **8766**；这不是上传服务无法监听。当前可访问 `http://127.0.0.1:8766/`，切回默认端口需用户在外部终止旧静态服务后启动上述命令。切换时也应停止临时应用实例，避免两个应用服务同时对同一任务发起重建。

### 用户流程与界面

1. 上传 KML 或 KMZ，创建 `jobs/<job_id>/`，原始上传写为 input.kml / input.kmz，源文件不修改或移动。
2. 请求立即返回任务 ID；最多两个任务并行处理，其余排队。页面每秒轮询，显示八阶段状态、说明和实际耗时。
3. 失败会保留阶段、原因、构建日志和重试入口；重新运行保留可人工修改的房屋判断表。中断的任务可重试。
4. 成功后自动进入该任务的三维预览。标题、日期、起终点名、记录里程来自上传文件；尺寸、比例、高度夸张来自本次模型，未将新任务写成雨崩示例。
5. 保留六个模型元素按钮（河流/湖泊、林区、草地、冰雪、房屋、海拔刻度）、独立照片开关/列表、透视/北向上/自动旋转/网格及 STL/3MF 下载。
6. 去掉左下角 footer。署名移入右侧面板底部默认收起的“数据来源”，保留 OSM ODbL、ESA WorldCover CC BY 4.0 和 Copernicus 署名。右下图例保留。来源问题和建筑判断路径在面板“生成说明”中展示；折叠项标题可见判断来源。
7. 照片任务可用“编辑房屋判断”修改 true / false / uncertain 及理由，保存后重建。不猜建筑真实位置，仍放在拍摄点。

### 自动数据与地理参数

上传解析位于 `app/tracks.py`，支持 gx:Track 或 LineString，提取 Document 名称、BeginTime/when 日期、PosStartName/PosEndName、Distance/Mileage、照片 FileId 等。当前两步路多段 Track 仍按导出顺序连接，记录潜在停录连接线警告。

UTM 由轨迹中心经纬度自动选择分区和南北半球；输入为 WGS84。范围由轨迹包围框加四周 1,100 m；最长边映射到全局打印目标 200 mm。DEM 由范围选择 1° Copernicus 瓦片，WorldCover 选择 3° 分幅，支持跨瓦片拼接裁剪；不把示例的 UTM 47N 或瓦片编号用于其他地区。默认高度夸张按 `clip(72 / (DEM高差 × mm_per_m), 1, 2)` 自动计算，必要时增厚底座以容纳低于 DSM 最低值的轨迹记录海拔。200 mm、1,100 m 和 72 mm 是本地产品的打印画幅/留边/目标起伏策略，不是地域常量。

任务 DEM 与 WorldCover 先按原始栅格裁剪，主构建器再按任务 CRS 重投影到模型网格。单个原始瓦片缓存于 `cache/`，裁剪、OSM 原始响应/查询/许可、照片原件与判断表全部写入任务的 `data/`。输入无高程时明确使用 DEM 回填首尾，不伪称 GPS 海拔。示例 CLI 不带 `--job-spec` 时保留原投影、比例与 1.25× 高度夸张。

### 八阶段及实现边界

| 阶段 | 实际工作 |
| --- | --- |
| 解析轨迹 | 安全读取 KML/KMZ，轨迹坐标/元信息/照片附件索引，计算投影与范围 |
| 获取地形数据 | 选择 DEM 瓦片，下载或验证真实缓存，按本次范围裁剪 |
| 3D 地形建模 | DEM 投影网格、自动比例/高程夸张、路线加密和距离场 |
| 河流与地表要素 | 获取 OSM / WorldCover，生成水体、林区、草地、雪冰掩膜及高程修改 |
| 照片点与房屋 | 提取 KMZ 原图、生成网页图，DEM 锚定，识别/推断建筑，生成房屋与路线断口 |
| 海拔刻度 | 按记录起终点海拔等分，生成选定侧壁的毫米级浮雕 |
| 导出与校验 | 地形/图钉/刻度布尔合并、STL/3MF 与共享缓冲写出、回读检查 |
| 网页预览 | 封装网页资产与照片数据、写最终元数据/通用下载链接，完成后发布任务 URL |

部分共享缓冲随导出写出，最后阶段负责封装和可访问发布，不将此前耗时算成浏览器渲染时间。

### 可插拔房屋判断

配置环境变量 `OPENAI_API_KEY` 后，使用 Responses API 上传任务派生的 JPEG 逐张判断建筑，结构化输出 has_house / reason；从终端启动服务前 `export OPENAI_API_KEY=...` 配置密钥（不要写入网页或仓库）；模型名可用 `OPENAI_VISION_MODEL` 覆盖，当前默认 `gpt-4.1-mini`。只发送待识别照片，不发送 API key 到浏览器；UI 已说明照片发送与潜在费用。格式依据官方文档：<https://developers.openai.com/api/docs/guides/images-vision>，结构化输出与图片请求合同通过 mock 测试，**本轮未配置 key、未执行真实付费模型请求**。

未配置 key 则走 `osm_nearby`：在照片拍摄点附近 **75 m** 内查 OSM building，记录最近距离和对象 ID。该判断仅说明附近有无已绘制建筑，不说明照片中是否看到了它；OSM 漏绘仍可能导致 false。查数失败则标 uncertain，默认不放屋。请求失败与模型错误不伪装成 false。

两条路径均写 `jobs/<job_id>/data/photo_houses.json`，记录坐标、来源、理由和判断；页面可改，重试优先保留现有表，不硬编码示例的 7/12/20/23/25 结果。人工修正后 method/source 标为 manual。没有照片时用 no_photos 分支，照片/房屋资源按任务实际情况显示。

### 实测端到端结果

测试入口：`HUAN_PATH_JOBS_DIR=/tmp/huan-jobs .venv/bin/python tests/e2e_upload.py --url http://127.0.0.1:8766`。它通过真实 HTTP 上传原只读文件、轮询至完成、下载 STL/3MF、请求预览资产与照片、核对源文件 SHA-256；不是仅调用构建脚本的模拟测试。结果文件 `work/upload-e2e-results.json`。

| 源文件 | 任务 ID | 总耗时 | 照片数 | 打印顶点 / 三角面 | 实体体积 |
| --- | --- | --- | --- | --- | --- |
| `2026-01-27-yubeng.kmz` | `20261021-210323-6e5a1b0e10` | 92.944 s | 28 | 258,692 / 517,380 | 876.185645 cm³ |
| `2026-09-17-yubeng.kml` | `20261021-210323-be03fc993b` | 85.347 s | 0 | 261,822 / 523,640 | 882.579614 cm³ |

| 阶段 | 2026-01-27 KMZ | 2026-09-17 KML |
| --- | --- | --- |
| 解析轨迹 | 0.069 s | 0.014 s |
| 获取地形数据 | 0.555 s | 0.513 s |
| 3D 地形建模 | 1.297 s | 0.579 s |
| 生成河流与地表要素 | 38.654 s | 76.141 s |
| 照片点与房屋 | 45.618 s | 1.265 s |
| 海拔刻度 | 0.046 s | 0.043 s |
| 导出与校验 | 6.698 s | 6.786 s |
| 生成网页预览 | 0.003 s | 0.005 s |

总耗时含调度及进程启动，可能与阶段耗时之和略有差异。两者均使用真实的本地区域 DEM/WorldCover 缓存；这些数字不代表首次下载网络性能。两任务均通过 STL/3MF 回读封闭、单组件、平底、Manifold 无错误，主轨迹分别为 **17,314 / 2,970 点**。KMZ 的 28 张照片全部解析并可访问，KML 无照片层。

本轮远程 Overpass 出现超时/502。水系与林地补充按地理交集复用已有署名 OSM 缓存，Jan 模型边界西侧比旧查询略宽，来源中明确标记部分覆盖；未覆盖处不虚构新要素。WorldCover 缓存正常。building 请求也未成功，KMZ 房屋走 OSM 分支但 **28 个均为 uncertain、实际放屋 0 个**；这不是视觉模型判定“没有房屋”。KML 为 no_photos、房屋 0。页面与原始来源文件保留这些警告。联网可用时重新判断需要移走/删除该任务的自动判断表再重试；普通重试优先保留表，避免覆盖人工修正。

### 校验、隔离与已知限制

- 雨崩示例原 STL/3MF 未覆盖。`work/example-regression-check.json` 记录：独立回归的 STL 字节一致，3MF 各 XML 内容一致（ZIP 时间戳可不同），默认打印文件哈希保持原样。
- `tests/test_inputs.py` 验证南半球 UTM、跨瓦片选择、KMZ/LineString、缺失高程和恶意 DTD 拒绝；`tests/test_vision.py` 验证视觉接口请求与返回合同，共七个单元测试通过（另含起终点海拔相同的刻度避让测试）。
- `tests/http_checks.py` 验证即时接收、失败/重试、房屋人工修正、跨域 Origin 限制和文件路径隔离；`tests/job-ui.mjs` 验证两任务动态标题/日期/下载、署名折叠、六类开关、刻度及 28 张照片标记/列表/弹窗/判断编辑器。
- `work/upload-page-validation.json` 验证上传页文件名编码、八阶段、成功自动跳转及失败重试入口；`work/upload-ui-validation.json` 为 DOM / Three.js 检查，不是 WebGL 浏览器截图。代理内未启动浏览器，截图仍由外部完成。
- 当前限制：上传 150 MB，KMZ 原始解压累计 800 MB、文件 2,500 个，KML 50 MB，轨迹最多 200,000 点、模型跨度 200 km、每任务照片最多 150 点。超限明确失败；不支持跨日期变更线或 UTM 极地范围，海区缺失 DEM 会失败，不伪造地形。
- 支持一般区域的自动选择不等于已在全球多区域实测；新区域冷下载、视觉真实账号、设备切片与实物打印仍未验收。失败的外部类别可降级并记明来源；DEM 缺失属于致命错误。
- 模型输入的日期/里程/记录海拔可能有误差，建筑推断与摄影点不是真实建筑测绘；现有陡坡嵌入、图钉尺度与打印兼容性限制继续适用。
- 本地服务只绑定 loopback，校验 Host/Origin，不是面向公网的认证、多用户或生产部署服务。只发布应用/作品资源，不提供整个项目目录的任意文件服务。

### 复现命令

```sh
.venv/bin/python tests/run_http_suite.py
```

该入口使用 `tempfile.mkdtemp()` 创建临时作品根，仅复制有 status.json 的已完成作品作为测试夹具（排除 models/；UI 只验证下载链接，不读取模型文件），以 `HUAN_PATH_JOBS_DIR=<临时目录>` 在 8766 启动服务，运行全部 Python 单元测试、job/upload/roads UI、HTTP、workbench/roads 浏览器检查；结束（含失败）关闭测试服务并删除临时目录。真实 `jobs/` 的目录列表和每个文件的 mtime/大小仅在内存中比较，打印 added/removed/changed 路径，不断言且不覆盖原始测试异常，不操作 8765。实网上传 `tests/e2e_upload.py` 会触发下载及共享缓存写入，隔离入口明确跳过，以保持 `cache/` 不变。

`HUAN_PATH_JOBS_DIR` 未设置时应用仍使用项目 `jobs/`；设置时 server、library、道路导入及流水线子进程共用该根目录（子进程继承环境）。例如：`HUAN_PATH_JOBS_DIR=/tmp/huan-jobs .venv/bin/python server.py --port 8766`。HTTP/实网上传测试要求显式指定真实库之外的 HUAN_PATH_JOBS_DIR，并与 8766 测试服务使用同一目录；脚本拒绝 8765。只读 UI 测试支持 `process.env.HUAN_PATH_JOBS_DIR || 'jobs'`，验证结果保存在 `work/`。

Node 测试使用已安装的 `work/browser-test/node_modules/`。重新部署完整项目时可在 `work/browser-test/` 运行 `npm ci` 恢复测试依赖，网页本身不需要 Node。


### 新增工程文件与接口

| 文件 | 作用 |
| --- | --- |
| `server.py` | 标准库 ThreadingHTTPServer、后台执行器、上传/进度/重试/编辑判断/资源隔离 |
| `app/tracks.py` | 有界 KML/KMZ 解析、元信息、自动 CRS/地理范围、规范化轨迹 |
| `app/datasets.py` | DEM / WorldCover 瓦片选择、缓存、拼接裁剪、OSM 获取及失败来源记录 |
| `app/photos.py` | 通用照片导入、投影/DEM 锚定、视觉/OSM 可插拔建筑判断 |
| `app/state.py` | 八阶段状态机和原子 JSON 状态文件 |
| `app/pipeline.py` | 独立任务编排、调用共享构建器、发布预览与下载 |
| `app/ui/` | 上传页、进度列表、作品历史 |
| `web/product-info.js` | 动态路线信息、来源说明、房屋人工修正入口 |
| `tests/` | 输入单元测试、视觉合同、HTTP 端到端、HTTP 错误/隔离和任务 UI 验证 |

构建复用方式：`build_model.py` 新增 `--job-spec jobs/<id>/spec.json`，从任务上下文读取 data_dir、EPSG、画幅、留边与路线上下文；通过阶段钩子接入进度、要素和照片准备。无 job-spec 时继续示例模式，不将本轮重构伪称为已经完全去掉脚本式入口。`feature_engine.py`、`elevation_scale.py` 继续处理统一元素及刻度，单任务用子进程隔离，避免同时修改全局参数。

| HTTP 接口 | 行为 |
| --- | --- |
| `GET /api/health` | 本地应用健康检查 |
| `POST /api/jobs?filename=...` | 原始二进制文件上传（非 multipart），202 返回任务 ID |
| `GET /api/jobs` | 作品/任务列表 |
| `GET /api/jobs/<id>` | 可轮询的阶段状态、耗时、错误与预览地址 |
| `POST /api/jobs/<id>/retry` | 重跑原任务，归档上次状态，保留人工判断表 |
| `GET/POST /api/jobs/<id>/houses` | 读取/修改判断；只更新状态和理由，保持坐标/照片编号 |
| `GET /jobs/<id>/web/` | 完成后发布的该任务网页与相对资源 |
| `GET /jobs/<id>/models/terrain.stl` / `terrain.3mf` | 该任务打印文件 |
| `GET /web/` | 兼容旧链接，重定向至已导入的正式作品 |

任务文件布局：`input.kml|kmz`、`status.json`、`spec.json`、`config.json`、`build.log`、`data/`、`models/`、`web/`；重试状态保存在 `attempts/`。所有 data 路径、照片、缓存派生掩膜均按任务隔离，只有原始瓦片缓存共享。新任务打印文件通用命名为 terrain.stl / terrain.3mf，不复用示例的名称作为作品标题。

进度由后台进程用临时文件 + os.replace 原子提交，前端每秒轮询；服务最多两个后台任务，HTTP 请求线程不等待建模完成。重启会将没有存活工作进程的未完成任务标为失败以便重试。新任务元数据不继承旧示例的人工房屋结果或历史几何验证摘要。

后续优先项：外部真实浏览器验收和多区域冷下载测试；完善 provider 重试/数据镜像及重新识别按钮；任务/缓存容量管理；按构建 ID 绑定验证而不是引用旧记录；去除示例兼容字段 `model_extent_utm47n`（新任务正确投影另存 `crs.epsg` 与 `model_extent_projected_m`）；正式函数化几何构建器和多段 Track 断段算法。


## 作品工作台改版（2026-10-21）

本节替代前述“独立上传页 + 示例入口”的页面设计。现在首页是一个作品工作台：左侧为作品列表，右侧为主体；没有选择作品时显示上传模块，选择完成作品时显示占满右侧内容区的三维预览。右上角“新建作品”和侧栏加号返回上传区。生成中的作品在右侧显示八阶段进度，完成后在同一工作台进入三维展示。

左侧可收起为图标导航，偏好保存在本机浏览器；窄屏使用可展开的抽屉。作品列表显示名称、日期、照片数、房屋数及待确认数量。现有三维页面的元素开关、视角、照片、房屋人工修正和下载继续保留。数据署名仍收纳于控制面板的折叠项中。

作品库只保留一件正式作品“雨崩 · 尼农线”，任务编号 `20261021-222421-be8fe509f3`；它由原有完成模型导入，包含 28 个照片点、5 个房屋（7、12、20、23、25），路线断口半径 4 mm。照片来自 2026-01-27，基础轨迹为 2026-09-17，仍明确提示日期不同。此前四个测试任务已按本次要求删除；原始数据、根目录打印成果和工程验证记录保留。迁移清单见 `work/library-migration.json`。历史端到端报告中的旧任务链接不再有效。

界面不再提供单独的“雨崩示例”入口；旧 `/web/` 地址重定向至该正式作品。访问首页不会自动选中作品，直接显示上传区；带 `?job=<id>` 的地址可直接打开作品，`&inspect=1` 查看阶段记录。

启动：双击 `start_preview.command`，或执行 `.venv/bin/python server.py --port 8766 --open`。启动脚本优先复用已经运行的 8766 / 8765 服务，否则在 8766 启动。当前服务地址为 `http://127.0.0.1:8766/`。

本次验证：七项 Python 单元测试通过；`tests/upload-ui.mjs` 检查作品切换、折叠持久化、迟到请求隔离、上传及失败重试；`tests/job-ui.mjs` 改为发现当前作品，检查动态信息、六类要素、照片与人工判断表。已对导入作品重新构建并核对：STL 字节与原成果一致，3MF 模型 XML 一致，封闭、单实体、平底与 Manifold 校验通过。真实浏览器工作台布局测试与 Three.js 数据/DOM 检查分开；本环境软件 WebGL 加载停滞，不将其声称为完整渲染验收。工作台真实浏览器布局与交互检查通过，收起导航后右侧宽度由测试视口下的 1172 px 扩大为 1368 px；HTTP 错误、重试、人工编辑和资源隔离检查通过。重建耗时 12.97 s。验证摘要见 `work/workbench-validation.json`。本轮未截图。

## 道路预览图层（2026-10-22）

道路支持系统代理、多镜像与 OSM 主 API 回退，网络预算见下文「Overpass 超时」（当前 Overpass 240 秒 + 主 API 60 秒）；失败记录原因并继续生成。`config/features.json` 的 `network.proxy` 优先于 HTTPS_PROXY / https_proxy / ALL_PROXY / all_proxy 与 macOS 系统代理；默认 null 自动选择，"off" 直连，回环直连。代理通过 curl `-K -` 的 stdin 配置传递，argv 与来源记录不含凭据。主 API 面积超限或 HTTP 400 切块，509 按普通失败处理。

新建作品可附加最大 50 MB 的 OSM JSON、XML 或 GeoJSON；已有作品可在预览中导入。文件优先使用作品 `data/roads_import.json`，不写共享在线缓存；缺节点的不完整 way 跳过，支持 UTF-8 BOM。附加道路导入失败会显示原因，作品仍启动生成。导入后复用流水线同步整套作品网页，不重建地形与打印文件。

道路四级保持暖色、最小屏幕目标宽度及模型宽度上限。每个 mesh 按 units 统一缩放，units 变化超过 5% 才重写 XY，旋转时不重写；道路、图钉与照片采样复用地形三角插值。道路仅用于预览，STL/3MF 道路几何留待后续拆分。实现与本轮验证见技术方案 §15。

本轮全部 25 项 Python 测试及六项 UI/浏览器/HTTP 检查通过。九月雨崩实网作品 `20261022-145941-34b4eefdfa` 经系统代理 127.0.0.1:7897，从 overpass-api.de 获取 122 条道路（非缓存）；20 条 curl argv 抽查均无代理串。HTTP 本地导入得到 121 条、cache 无新增且打印文件哈希不变；坏道路文件返回 400 后 retry 的作品 `20261022-145851-21aacdab8e` 完成。记录见 `work/roads-round3-*.json` 与 `work/roads-round3-ps.txt`。8765 未操作，8766 测试服务验证后关闭。

## 地名标签、居民区图层与作品搜索（2026-10-26）

### 地名与居民区（仅网页预览）

- 流水线在 STL/3MF 导出**之后**经 Overpass 取 `place=city|town|village|hamlet|locality` 节点和 `landuse=residential|commercial|retail|industrial` 面，写入作品 `web/layers/places.json`（最多 400 个，按级别和人口排序）与 `web/layers/settlements.bin`（与 `classes.bin` 同网格的 uint8 分类）。metadata 中 `preview_layers.places / settlements` 是唯一的图层地址，`settlements` 记录计数、样式与 ODbL 来源。
- 打印文件不含这两层；取数或构建失败只写入一条警告并得到空图层，绝不阻断打印文件、不虚构数据。
- 预览中「地名」「居民区」两个开关即时切换。标签按级别贪心避让，并沿视线对预览高度场做光线步进，被山体挡住的标签隐藏（相机移动时最多每 120 ms 重算一次，停下后再补算一次）。
- 已有作品补建或刷新：`.venv/bin/python -m app.settlements [--assets] <作品目录>...`。只改 `web/` 图层、metadata 与 `spec.json` 警告，不动 `models/` 打印文件；`--assets` 另外调用 `pipeline.package_preview` 同步当前网页代码。

### Overpass 超时

`app/datasets.py`：服务器端 `[timeout:90]`，单次客户端尝试 105 秒，全部镜像共享 240 秒总预算；道路与地名/居民区查询另留 60 秒给 OSM 主 API 回退。剩余预算不足 20 秒不再尝试。完整用满 105 秒仍无响应的镜像在本进程内排到最后；被预算截短的尝试不降级镜像。缓存键沿用旧的 `[timeout:25]` 查询文本，因此调整超时不会让已有缓存失效。

已知限制：OSM 主 API 回退（`/api/0.6/map` 切块）只保留 way 与带标签节点，**丢弃 relation**（多边形关系形式的居民区/水面在回退时缺失）；回退的合并结果按该查询写入缓存，但 `/map` 块本身不缓存：同一范围的道路与地名/居民区查询各自回退时会重复下载相同的块。

### 作品搜索

工作台左侧作品栏去掉「新增作品」按钮，改为按名称（及原文件名）模糊搜索：忽略大小写、全半角与空白，前缀匹配排最前，其次子串，再次按顺序包含所有字符；输入法组字期间不过滤，Esc 或 × 清空，计数显示「匹配数/总数」。折叠侧栏时自动清空搜索；折叠状态下点放大镜展开侧栏。上传入口仍在工具栏「＋ 新建作品」、左上角品牌与默认上传页。

# Site_Drainage_Model CA2D 静态模型改造

- 网格：150 × 145；分辨率 3 m；有效单元 12974。
- 建筑：56 栋推测轮廓，966 个单元；相对原地面抬高 15 m，排除出过流域。
- 道路：6 条底图推测中心线，2569 个单元；宽 8–10 m，下凹 0.10 m。
- 道路/其他土地过流系数：0.90 / 0.62（代码中的 resistance 数值越大，过流越强）。
- 耦合：12 个节点全部映射至非建筑过流单元；最大距离 11.99 m。
- terrain.npy 保存未叠加道路/建筑的原地面，elevation.npy 是实际求解高程。
- 建筑避开道路及周边 3 m、节点周边 6 m；中央公园和排水廊道未作为建筑地块。

位置依据 swmm/Site-Post.jpg 和 SWMM [BACKDROP] 范围配准。底图展示地块，不能确定真实建筑轮廓；
楼高、道路宽度、下凹量与建筑占地均为可修改的建模假设，保存在 raw/references/site_layout_reference.json。
未修改 SWMM 场景、降雨文件或既有运行结果；既有结果不会自动更新，需要重新运行 CA2D。

重建命令：`python models/Site_Drainage_Model/scripts/build_site_ca2d.py`。

# CA2D 静态数据

20 m、580×364 区域基础网格；完整构造方法与用途边界见 ../README.md 和 config.json。

terrain.npy 是井口高程插值及锚定后的基底；elevation.npy 另含走廊降低和障碍抬高。flow_mask 排除障碍和无效域；cell_id_grid 从 0 编号，无效格 -1，smid_grid 从 1 编号，无效格 0。node_to_cell_mapping.csv 含全部 113 个节点。

布局图不是降雨结果；ca2d_smoke_test.png 为人工 2 L/s/井、10 min 注水验收，不代表任何真实降雨场景。synthetic_streets.csv 与 synthetic_buildings.csv 是构造资料，不是现场测绘。

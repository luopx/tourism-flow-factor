import os
from pathlib import Path

# 获取项目根目录 (假设运行路径为 code/ 目录下，根目录为上一级)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 数据相关路径
DATA_DIR = PROJECT_ROOT / 'data'
AOI_DIR = DATA_DIR / 'AOI'
RAW_TRAJ_DIR = DATA_DIR / 'raw_trajectory'
CLEANED_TRAJ_DIR = DATA_DIR / 'cleaned_trajectory'
STOCK_FINANCE_DIR = DATA_DIR / 'finance'

# 输出文件路径
OUTPUT_DIR = PROJECT_ROOT / 'output'
TMP_DIR = PROJECT_ROOT / 'tmp'

# 图表输出路径
FIGURES_DIR = PROJECT_ROOT / 'figures'

# 确保所有基础目录存在
for d in [DATA_DIR, AOI_DIR, RAW_TRAJ_DIR, CLEANED_TRAJ_DIR, STOCK_FINANCE_DIR, OUTPUT_DIR, TMP_DIR, FIGURES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# 并发配置
MAX_WORKERS = min(32, os.cpu_count() or 4)

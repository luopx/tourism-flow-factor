import os
import glob
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from multiprocessing import Pool
import warnings

from config import AOI_DIR, RAW_TRAJ_DIR, OUTPUT_DIR, MAX_WORKERS

warnings.filterwarnings("ignore")

# 全局变量供多进程使用
global_aoi_gdf = None
global_aoi_bounds = None

def init_worker():
    """初始化工作进程的全局变量，避免多次加载"""
    global global_aoi_gdf, global_aoi_bounds
    
    aoi_files = glob.glob(os.path.join(AOI_DIR, "*.shp"))
    gdfs = []
    bounds = []
    for f in aoi_files:
        name = os.path.basename(f).replace('.shp', '')
        gdf = gpd.read_file(f)
        gdf['location'] = name
        gdfs.append(gdf[['location', 'geometry']])
        if not gdf.empty:
            minx, miny, maxx, maxy = gdf.total_bounds
            bounds.append((minx, miny, maxx, maxy))
            
    if gdfs:
        global_aoi_gdf = pd.concat(gdfs, ignore_index=True)
        global_aoi_gdf = global_aoi_gdf.to_crs("EPSG:4326")
        _ = global_aoi_gdf.sindex
        global_aoi_bounds = bounds
    else:
        global_aoi_gdf = gpd.GeoDataFrame(columns=['location', 'geometry'], crs="EPSG:4326")
        global_aoi_bounds = []

def process_trajectory_file(file_path):
    columns_to_keep = ['tid', 'createTime', 'lng', 'lat', 'elev', 'speed']
    try:
        # 优先读取 uid，保持与后续按用户去重口径一致。
        df_all = pd.read_parquet(file_path, columns=columns_to_keep + ['uid'])
        uid_from_source = True
    except Exception:
        try:
            # 兼容无 uid 的数据：退化为 tid 作为用户标识，避免流程中断。
            df_all = pd.read_parquet(file_path, columns=columns_to_keep)
            df_all['uid'] = df_all['tid']
            uid_from_source = False
        except Exception as e:
            print(f"读取文件错误 {file_path}: {e}")
            return

    if df_all.empty:
        return

    # 1. 粗筛
    lng = df_all['lng'].values
    lat = df_all['lat'].values
    in_bounds = np.zeros(len(df_all), dtype=bool)
    
    for minx, miny, maxx, maxy in global_aoi_bounds:
        in_bounds |= ((lng >= minx) & (lng <= maxx) & (lat >= miny) & (lat <= maxy))

    points_in_bounds = df_all[in_bounds]
    if points_in_bounds.empty:
        return
        
    tid_counts = points_in_bounds.groupby('tid').size()
    target_tids = tid_counts[tid_counts >= 3].index
    
    if len(target_tids) == 0:
        return

    df_filtered = df_all[df_all['tid'].isin(target_tids)]

    # 2. 细筛与属性提取
    results = []
    for tid, df_group in df_filtered.groupby('tid'):
        df = df_group.copy().sort_values('createTime').reset_index(drop=True)
        
        geometry = [Point(xy) for xy in zip(df['lng'], df['lat'])]
        points_gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
        
        joined = gpd.sjoin(points_gdf, global_aoi_gdf, how="left", predicate="within")
        df['location'] = joined['location']
        
        points_in_aoi = df['location'].notna().sum()
        if points_in_aoi < 3:
            continue

        # 时间修正后，只保留 AOI 内点位，便于后续按 uid/date/location 去重。
        df['createTime'] = pd.to_datetime(df['createTime']) + pd.Timedelta(hours=8)
        in_aoi_df = df[df['location'].notna()].copy()
        in_aoi_df['date'] = in_aoi_df['createTime'].dt.date
        results.append(in_aoi_df[['uid', 'tid', 'createTime', 'date', 'location']])

    if results:
        res_df = pd.concat(results, ignore_index=True)
        res_df = res_df.drop_duplicates(subset=['uid', 'tid', 'createTime', 'date', 'location'])

        # 使用相对路径生成文件名，避免不同子目录同名 parquet 相互覆盖。
        rel_path = os.path.relpath(file_path, RAW_TRAJ_DIR)
        safe_name = rel_path.replace(os.sep, '__')
        out_path = os.path.join(OUTPUT_DIR, f"extracted_{safe_name}")
        res_df.to_parquet(out_path, index=False)

        if not uid_from_source:
            print(f"警告：{file_path} 缺少 uid 字段，已使用 tid 作为替代。")

def main():
    traj_files = glob.glob(os.path.join(RAW_TRAJ_DIR, "**", "*.parquet"), recursive=True)
    
    with Pool(processes=MAX_WORKERS, initializer=init_worker) as pool:
        pool.map(process_trajectory_file, traj_files)
        
    print("轨迹提取与属性扩充完成。")

if __name__ == "__main__":
    main()
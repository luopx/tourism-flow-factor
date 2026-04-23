import os
import glob
import pandas as pd
from config import OUTPUT_DIR, CLEANED_TRAJ_DIR

def merge_and_deduplicate():
    print("开始合并并去重...")
    
    os.makedirs(CLEANED_TRAJ_DIR, exist_ok=True)

    # 汇总 02 输出的明细数据（字段口径以 uid/date/location 为核心）
    extracted_files = glob.glob(os.path.join(OUTPUT_DIR, "extracted_*.parquet"))
    if not extracted_files:
        print("未找到需要合并的文件！")
        return
        
    df_list = []
    # 这里可以使用分块合并逻辑
    for f in extracted_files:
        try:
            cur_df = pd.read_parquet(f)
            if cur_df.empty:
                continue

            # 兼容旧版输出结构：若无 date 则从时间字段生成。
            if 'date' not in cur_df.columns:
                if 'createTime' in cur_df.columns:
                    cur_df['date'] = pd.to_datetime(cur_df['createTime']).dt.date
                elif 'start_time' in cur_df.columns:
                    cur_df['date'] = pd.to_datetime(cur_df['start_time']).dt.date
                else:
                    print(f"跳过文件（缺少 date/createTime/start_time）: {f}")
                    continue

            # 兼容无 uid 的历史文件。
            if 'uid' not in cur_df.columns:
                if 'tid' in cur_df.columns:
                    cur_df['uid'] = cur_df['tid']
                    print(f"警告：{f} 缺少 uid，已使用 tid 作为替代。")
                else:
                    print(f"跳过文件（缺少 uid/tid）: {f}")
                    continue

            required_cols = {'uid', 'date', 'location'}
            if not required_cols.issubset(cur_df.columns):
                print(f"跳过文件（缺少必需字段）: {f}")
                continue

            keep_cols = [c for c in ['uid', 'tid', 'createTime', 'date', 'location'] if c in cur_df.columns]
            cur_df = cur_df[keep_cols]
            cur_df = cur_df[cur_df['location'].notna()].copy()

            if not cur_df.empty:
                df_list.append(cur_df)
        except Exception as e:
            print(f"读取异常: {f} | {e}")
            
    if not df_list:
        print("未找到可用数据，流程结束。")
        return
        
    final_df = pd.concat(df_list, ignore_index=True)

    print("总计获取记录数: ", len(final_df))

    final_df['date'] = pd.to_datetime(final_df['date']).dt.date
    final_df = final_df.drop_duplicates(subset=['uid', 'date', 'location']).reset_index(drop=True)
    final_df = final_df.sort_values(['date', 'location', 'uid']).reset_index(drop=True)

    out_path = os.path.join(CLEANED_TRAJ_DIR, "final_tourists_uv.parquet")
    compat_out_path = os.path.join(CLEANED_TRAJ_DIR, "合并_按照用户-日期-aoi去重.parquet")
    final_df.to_parquet(out_path, index=False)
    final_df.to_parquet(compat_out_path, index=False)
    print(f"规整完成，已保存至: {out_path}")
    print(f"兼容文件已保存至: {compat_out_path}")

if __name__ == "__main__":
    merge_and_deduplicate()
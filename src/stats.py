import pandas as pd
import os
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json


class StatisticsManager:
    def __init__(self, log_path: str = "data/logs/intrusion_history.csv"):
        self.log_path = log_path

    def get_daily_stats(self, days: int = 7) -> Dict:
        """获取指定天数的每日统计数据"""
        if not os.path.exists(self.log_path):
            return {}

        df = self._load_dataframe()
        if df.empty:
            return {}

        # 确保Time列是datetime类型
        df['Time'] = pd.to_datetime(df['Time'], format='%Y-%m-%d %H:%M:%S', errors='coerce')

        # 过滤最近几天的数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        filtered_df = df[(df['Time'] >= start_date) & (df['Time'] <= end_date)]

        # 按日期分组统计
        daily_stats = filtered_df.groupby(filtered_df['Time'].dt.date).size().to_dict()

        # 确保所有天都有数据
        result = {}
        for i in range(days):
            date = (end_date - timedelta(days=i)).date()
            result[date.isoformat()] = daily_stats.get(date, 0)

        return result

    def get_top_intruders(self, limit: int = 10) -> List[Dict]:
        """获取频繁闯入的目标ID"""
        if not os.path.exists(self.log_path):
            return []

        df = self._load_dataframe()
        if df.empty:
            return []

        # 按Pet_ID分组统计次数
        intruder_counts = df['Pet_ID'].value_counts().head(limit)

        result = []
        for pet_id, count in intruder_counts.items():
            result.append({
                'pet_id': pet_id,
                'count': int(count)
            })

        return result

    def get_hourly_pattern(self) -> Dict[int, int]:
        """获取按小时的闯入模式统计"""
        if not os.path.exists(self.log_path):
            return {}

        df = self._load_dataframe()
        if df.empty:
            return {}

        df['Time'] = pd.to_datetime(df['Time'], format='%Y-%m-%d %H:%M:%S', errors='coerce')

        # 按小时提取数据
        hourly_counts = df.groupby(df['Time'].dt.hour).size().to_dict()

        # 确保24小时都有数据
        result = {hour: 0 for hour in range(24)}
        result.update(hourly_counts)

        return result

    def get_total_stats(self) -> Dict:
        """获取总体统计数据"""
        if not os.path.exists(self.log_path):
            return {
                'total_events': 0,
                'unique_pets': 0,
                'first_event': None,
                'last_event': None
            }

        df = self._load_dataframe()
        if df.empty:
            return {
                'total_events': 0,
                'unique_pets': 0,
                'first_event': None,
                'last_event': None
            }

        df['Time'] = pd.to_datetime(df['Time'], format='%Y-%m-%d %H:%M:%S', errors='coerce')

        return {
            'total_events': len(df),
            'unique_pets': df['Pet_ID'].nunique(),
            'first_event': df['Time'].min().isoformat() if not df['Time'].empty else None,
            'last_event': df['Time'].max().isoformat() if not df['Time'].empty else None
        }

    def _load_dataframe(self) -> pd.DataFrame:
        """加载CSV数据到DataFrame"""
        try:
            df = pd.read_csv(self.log_path)
            return df
        except Exception:
            # 如果读取失败，返回空DataFrame
            return pd.DataFrame(columns=['Time', 'Pet_ID', 'Image_File', 'Status'])
import os
import csv
from datetime import datetime


class CaptureHistoryManager:
    def __init__(self, base_path="data"):
        self.base_path = base_path
        self.image_path = os.path.join(base_path, "images")
        self.log_path = os.path.join(base_path, "logs")
        self.log_file = os.path.join(self.log_path, "intrusion_history.csv")

    def delete_capture_record(self, image_filename, delete_file=True):
        """
        删除抓拍记录

        Args:
            image_filename: 要删除的图片文件名
            delete_file: 是否同时删除图片文件

        Returns:
            bool: 操作是否成功
        """
        try:
            # 从CSV日志中删除对应记录
            temp_log_file = self.log_file + ".tmp"

            with open(self.log_file, 'r', encoding='utf-8') as infile, \
                 open(temp_log_file, 'w', newline='', encoding='utf-8') as outfile:

                reader = csv.DictReader(infile)
                fieldnames = reader.fieldnames
                writer = csv.DictWriter(outfile, fieldnames=fieldnames)
                writer.writeheader()

                for row in reader:
                    if row['Image_File'] != image_filename:
                        writer.writerow(row)

            # 替换原文件
            os.replace(temp_log_file, self.log_file)

            # 删除实际的图片文件
            if delete_file:
                image_full_path = os.path.join(self.image_path, image_filename)
                if os.path.exists(image_full_path):
                    os.remove(image_full_path)

            return True
        except Exception as e:
            print(f"删除抓拍记录失败: {str(e)}")
            # 如果临时文件存在，清理它
            temp_log_file = self.log_file + ".tmp"
            if os.path.exists(temp_log_file):
                os.remove(temp_log_file)
            return False

    def get_capture_count_by_date_range(self, start_date=None, end_date=None):
        """
        获取指定日期范围内的抓拍数量

        Args:
            start_date: 开始日期 (datetime对象)
            end_date: 结束日期 (datetime对象)

        Returns:
            int: 抓拍数量
        """
        count = 0
        try:
            if not os.path.exists(self.log_file):
                return count

            with open(self.log_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    time_str = row.get('Time', '')
                    if time_str:
                        record_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')

                        # 检查日期范围
                        if start_date and record_time < start_date:
                            continue
                        if end_date and record_time > end_date:
                            continue

                        count += 1
        except Exception as e:
            print(f"获取抓拍数量失败: {str(e)}")

        return count

    def get_unique_pet_ids(self):
        """
        获取所有唯一的宠物ID

        Returns:
            set: 唯一宠物ID集合
        """
        pet_ids = set()
        try:
            if not os.path.exists(self.log_file):
                return pet_ids

            with open(self.log_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    pet_id = row.get('Pet_ID', '')
                    if pet_id:
                        pet_ids.add(pet_id)
        except Exception as e:
            print(f"获取唯一宠物ID失败: {str(e)}")

        return pet_ids

    def search_records(self, search_term="", pet_id_filter="", start_date=None, end_date=None):
        """
        搜索抓拍记录

        Args:
            search_term: 搜索关键词
            pet_id_filter: 宠物ID过滤器
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            list: 符合条件的记录列表
        """
        results = []
        try:
            if not os.path.exists(self.log_file):
                return results

            with open(self.log_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    time_str = row.get('Time', '')
                    pet_id = row.get('Pet_ID', '')
                    image_file = row.get('Image_File', '')

                    # 时间解析
                    record_time = None
                    if time_str:
                        record_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')

                    # 应用过滤器
                    if start_date and record_time and record_time < start_date:
                        continue
                    if end_date and record_time and record_time > end_date:
                        continue
                    if pet_id_filter and pet_id_filter.lower() not in pet_id.lower():
                        continue
                    if search_term:
                        search_term_lower = search_term.lower()
                        if (search_term_lower not in time_str.lower() and
                            search_term_lower not in pet_id.lower() and
                            search_term_lower not in image_file.lower()):
                            continue

                    results.append(row)
        except Exception as e:
            print(f"搜索抓拍记录失败: {str(e)}")

        return results
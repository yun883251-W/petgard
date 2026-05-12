import sys
import os
import pandas as pd
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
                             QVBoxLayout, QPushButton, QWidget, QHeaderView, QMessageBox)
from PyQt6.QtCore import Qt


class HistoryWindow(QMainWindow):
    def __init__(self, log_path, video_dir):
        super().__init__()
        self.log_path = log_path
        self.video_dir = video_dir

        self.setWindowTitle("宠物违规历史记录查询系统")
        self.resize(800, 500)

        # 主布局
        self.layout = QVBoxLayout()

        # 表格初始化
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["违规时间", "宠物 ID", "视频文件名", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # 刷新按钮
        self.btn_refresh = QPushButton("刷新数据")
        self.btn_refresh.clicked.connect(self.load_data)
        self.btn_refresh.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px;")

        self.layout.addWidget(self.btn_refresh)
        self.layout.addWidget(self.table)

        container = QWidget()
        container.setLayout(self.layout)
        self.setCentralWidget(container)

        self.load_data()

    def load_data(self):
        """从 CSV 加载数据到表格"""
        if not os.path.exists(self.log_path):
            QMessageBox.warning(self, "提醒", "暂无历史记录文件。")
            return

        # 读取 CSV
        try:
            df = pd.read_csv(self.log_path)
            # 按时间倒序排序（最新的在上面）
            df = df.iloc[::-1]

            self.table.setRowCount(len(df))
            for i, (index, row) in enumerate(df.iterrows()):
                self.table.setItem(i, 0, QTableWidgetItem(str(row['Time'])))
                self.table.setItem(i, 1, QTableWidgetItem(str(row['Pet_ID'])))
                self.table.setItem(i, 2, QTableWidgetItem(str(row['Video_File'])))

                # 添加播放按钮
                btn_play = QPushButton("点击回放")
                btn_play.clicked.connect(lambda ch, r=row['Video_File']: self.play_video(r))
                self.table.setCellWidget(i, 3, btn_play)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载失败: {e}")

    def play_video(self, filename):
        """调用系统播放器播放视频"""
        video_full_path = os.path.join(self.video_dir, filename)
        if os.path.exists(video_full_path):
            # Windows 下调用默认播放器
            os.startfile(video_full_path)
        else:
            QMessageBox.critical(self, "错误", f"找不到视频文件: {filename}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # 测试路径
    LOG = r"E:\prprojets\PetGuard_System\data\logs\intrusion_history.csv"
    VIDEO = r"E:\prprojets\PetGuard_System\data\videos"

    window = HistoryWindow(LOG, VIDEO)
    window.show()
    sys.exit(app.exec())
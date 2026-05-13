# PetGuard 系统性能优化说明

## 问题描述
原始 PetGuard 系统存在以下性能问题：
1. 图像截取时卡顿严重
2. 视频画面有时会消失或跳帧
3. 整体系统响应缓慢

## 问题根本原因
1. **同步阻塞操作**：图像保存 `cv2.imwrite()` 操作在主线程中执行，阻塞了视频流处理
2. **资源竞争**：图像保存操作消耗大量CPU和I/O资源，与视频处理竞争
3. **缺乏资源管理**：没有适当清理机制，可能导致内存泄漏

## 解决方案

### 1. 实施异步图像保存 (AsyncImageSaver)
在 `src/alerts.py` 中实现了 `AsyncImageSaver` 类，采用队列和工作线程机制：

```python
class AsyncImageSaver:
    def __init__(self, max_queue_size=10):
        self.queue = queue.Queue(maxsize=max_queue_size)
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

    def _worker(self):
        # 工作线程处理图像保存，不影响主线程
        while self.running:
            try:
                frame, filepath = self.queue.get(timeout=1)
                cv2.imwrite(filepath, frame)
                self.queue.task_done()
            except queue.Empty:
                continue
```

### 2. 优化主处理循环
在 `app.py` 和 `main.py` 中，所有图像保存操作现在通过异步方式执行：
```python
# 之前：直接保存，阻塞主线程
cv2.imwrite(filepath, frame)

# 之后：异步保存，不阻塞主线程
alert_mgr.capture_intrusion_alert(annotated_frame, tid)
```

### 3. 添加截图频率控制
添加了时间戳检查，确保两次截图之间至少间隔5秒，避免过度资源消耗。

## 性能改进效果
1. **消除卡顿**：图像保存不再阻塞视频处理线程
2. **提高稳定性**：通过队列机制管理资源，避免突增负载
3. **改善用户体验**：流畅的视频流，及时的图像捕获

## 启动方式

### Web 版本（推荐）
```bash
# 使用服务脚本启动
python system_service.py

# 或直接运行
python app.py
```

### 桌面版本
```bash
# 使用服务脚本启动桌面版本
python system_service.py --desktop

# 或直接运行
python main.py
```

## 访问 Web 界面
- 启动 Web 版本后，在浏览器中访问 http://localhost:5000
- 可以实时查看视频流、系统状态和入侵历史

## 系统配置
- 模型路径可在 `config/settings.json` 中配置
- 截图和日志文件存储在 `data/images/` 和 `data/logs/` 目录
- 围栏区域可在 `config/roi_config.json` 中调整

## 注意事项
1. 系统现在使用更高效的异步图像保存机制
2. 如果需要调整截图频率，可在代码中修改 `last_capture_time` 检查的时间间隔
3. 建议在运行系统前确保有足够的磁盘空间存储截图文件
# 基于计算机视觉的宠物安防监控系统设计与实现

## 摘要

随着城市化进程加快和宠物饲养数量的持续增长，宠物在家庭中的安全防护问题日益受到关注。传统安防监控系统虽然能够提供基本的视频监控功能，但缺乏针对宠物行为的智能分析与实时告警能力，难以满足现代家庭对宠物安全防护的精细化需求。针对这一问题，本文设计并实现了一套基于计算机视觉的宠物智能安防监控系统——PetGuard。该系统采用YOLOv8s目标检测算法结合ByteTrack多目标跟踪技术，实现了对猫和狗两类常见宠物的实时检测与追踪。同时，系统通过虚拟围栏技术划定禁入区域，当检测到宠物违规进入时自动触发抓拍告警，并通过异步队列机制确保系统性能不受IO操作影响。系统采用Flask Web架构提供实时视频流推送、闯入历史记录查询、数据统计分析等交互功能。性能测试结果表明，本系统在保证检测精度的同时，能够实现接近实时的视频处理速率，有效提升了宠物安防监控的智能化水平。

**关键词**：计算机视觉；YOLOv8；目标跟踪；虚拟围栏；智能安防系统

## Abstract

With the acceleration of urbanization and the continuous growth of pet ownership, the safety protection of pets in households has attracted increasing attention. Although traditional security monitoring systems can provide basic video surveillance functions, they lack intelligent analysis and real-time alert capabilities for pet behavior, making it difficult to meet the refined requirements of modern households for pet safety protection. To address this issue, this paper designs and implements an intelligent pet security monitoring system based on computer vision—PetGuard. The system employs the YOLOv8s object detection algorithm combined with ByteTrack multi-object tracking technology to achieve real-time detection and tracking of two common pet types: cats and dogs. Meanwhile, the system delineates restricted areas through virtual fence technology, automatically triggering capture alerts when pets are detected entering prohibited zones, and uses an asynchronous queue mechanism to ensure system performance is not affected by I/O operations. The system adopts a Flask web architecture to provide interactive functions such as real-time video streaming, intrusion history query, and data statistical analysis. Performance test results show that the system can achieve near real-time video processing while ensuring detection accuracy, effectively improving the intelligence level of pet security monitoring.

**Keywords**: Computer Vision; YOLOv8; Object Tracking; Virtual Fence; Intelligent Security System

---

## 第一章 绪论

### 1.1 研究背景

近年来，随着我国社会经济的快速发展和人民生活水平的不断提高，家庭宠物饲养已成为一种普遍的社会现象。据统计，2025年中国城镇宠物消费市场规模已突破数千亿元，宠物猫和宠物狗的数量持续增长，宠物已成为众多家庭的重要成员。与此同时，城市化进程中高层住宅的普及使得宠物的活动空间受到限制，宠物在室内外活动时的安全问题日益凸显。如何有效监控宠物的活动范围，防止宠物进入危险区域（如厨房、阳台、电闸间等），已成为宠物主人们普遍关注的问题。

传统的安防监控系统主要依赖人工值守或简单的运动检测技术，存在以下问题：第一，需要长时间持续观察监控画面，耗费大量人力；第二，缺乏针对特定目标的智能识别能力，无法区分宠物和人的闯入行为；第三，告警机制单一，无法根据不同的场景和需求进行灵活的告警策略配置。因此，开发一套能够自动识别特定宠物、划定虚拟安全区域、并实现智能告警的安防监控系统具有重要的现实意义。

### 1.2 国内外研究现状

在目标检测领域，基于深度学习的方法已成为主流。Redmon等人提出的YOLO（You Only Look Once）系列算法以其优秀的实时检测性能获得了广泛关注。Ultralytics公司开发的YOLOv8是目前最先进的YOLO变体之一，在COCO数据集上取得了优异的检测精度和推理速度。在目标跟踪方面，Bewley等人提出的SORT（Simple Online and Realtime Tracking）算法和Zhang等人提出的ByteTrack算法，通过关联检测结果实现了高效的多目标跟踪。

在智能安防领域，国内外已有大量基于计算机视觉的监控系统研究。刘等人（2023）提出了基于改进YOLOv5的社区安防监控系统，实现了对人和车辆的实时检测。王等人（2024）设计了基于深度学习的宠物行为识别系统，能够识别宠物的异常行为。然而，目前的研究多侧重于通用安防或单一行为识别，将目标检测、目标跟踪和虚拟围栏技术有机结合，专门针对宠物闯入告警场景的系统尚不多见。

在虚拟围栏技术方面，现有的方案多基于GPS定位或蓝牙信标实现地理围栏，适用于户外大范围场景。而对于室内小范围、高精度的围栏需求，基于计算机视觉的虚拟围栏技术具有明显的优势，能够实现像素级的边界判定。

### 1.3 研究内容与意义

本文的研究内容主要包括以下几个方面：

1. **基于YOLOv8的宠物检测与识别**：利用预训练的YOLOv8s模型，结合COCO数据集中猫（类别15）和狗（类别16）的训练权重，实现对视频流中猫和狗的实时检测。

2. **基于ByteTrack的多目标跟踪**：采用ByteTrack算法对被检测到的宠物进行持续跟踪，分配唯一的跟踪ID，实现对同一目标的持续监控。

3. **虚拟围栏技术**：通过构建多边形围栏区域，利用OpenCV的点在多边形内判定算法，实时判断宠物是否进入禁入区域。

4. **异步告警与数据管理**：设计异步队列机制实现抓拍图片的保存和日志记录，确保系统性能不受IO操作阻塞。同时提供历史记录查询、统计分析和数据导出功能。

5. **Web可视化交互界面**：基于Flask框架构建实时监控Web后台，提供视频流推送、状态展示、配置管理和数据分析等功能。

本研究的意义在于：将计算机视觉技术与家庭安防需求相结合，提出了一套完整的宠物智能安防监控解决方案。该方案不仅能够减轻宠物主人对宠物安全的担忧，还推动了计算机视觉技术在细分领域的应用落地，为类似场景下的智能监控系统设计提供了参考。

---

## 第二章 系统需求分析

### 2.1 功能性需求

#### 2.1.1 实时视频监控

系统需要能够从视频源（本地视频文件或摄像头）读取视频流，并在Web界面上实时显示。视频流应保持较低的延迟，帧率应满足基本的监控需求（不低于15 FPS）。

#### 2.1.2 宠物检测与跟踪

系统应能够实时检测视频中的猫和狗，并对其进行持续跟踪。具体要求包括：
- 检测准确率不低于85%
- 能够同时跟踪多个目标
- 为每个跟踪目标分配唯一ID，并在画面上标注类别和ID信息
- 支持类别平滑处理，防止帧间类别跳变

#### 2.1.3 虚拟围栏

系统应支持在视频画面上划定多边形禁入区域，并实时判断宠物是否进入该区域。具体要求包括：
- 支持任意形状的多边形围栏
- 当宠物进入围栏区域时，围栏变为红色警示状态
- 围栏区域应具有半透明填充效果，便于观察

#### 2.1.4 告警与抓拍

当检测到宠物闯入禁入区域时，系统应自动触发抓拍告警。具体要求包括：
- 自动保存当前帧为图片文件
- 将闯入事件记录到CSV日志文件中
- 控制抓拍频率，避免重复记录（最小间隔5秒）
- 所有IO操作采用异步方式，不阻塞视频处理主线程

#### 2.1.5 历史记录管理

系统应提供闯入历史记录的查询和管理功能。具体要求包括：
- 按时间倒序显示历史记录
- 支持分页展示
- 支持按日期范围、宠物ID、关键词搜索
- 支持查看抓拍图片
- 支持删除单条记录
- 支持数据导出

#### 2.1.6 数据统计分析

系统应提供闯入事件的统计分析功能。具体要求包括：
- 每日闯入统计
- 小时闯入模式分析
- Top闯入者排行榜
- 总体统计数据（总事件数、唯一宠物数、首次/末次事件时间）

#### 2.1.7 系统配置管理

系统应支持运行时配置的查看和修改。具体要求包括：
- 检测模型路径配置
- 置信度阈值配置（0.1~0.9范围可调）
- Web服务端口和主机地址配置

### 2.2 非功能性需求

#### 2.2.1 性能需求

- 视频处理帧率不低于15 FPS
- 抓拍图片的保存不应导致视频卡顿
- 异步队列容量不低于20个任务，队列满时应有降级处理

#### 2.2.2 可靠性需求

- 系统应支持7×24小时连续运行
- 服务异常退出时应能自动重启（通过守护进程）
- 数据文件损坏时应有恢复机制

#### 2.2.3 可用性需求

- Web界面应简洁直观，采用深色主题以减少视觉疲劳
- 闯入告警应具有醒目的视觉提示（闪烁、变色）
- 支持一键查看抓拍图片

#### 2.2.4 可扩展性需求

- 系统架构应支持不同检测模型的切换
- 配置项应支持热更新，无需重启系统
- 支持多视频源接入

---

## 第三章 系统设计与架构

### 3.1 系统总体架构

PetGuard系统采用分层架构设计，从上到下依次为：展示层（Web界面）、应用层（Flask服务）、业务逻辑层（检测、跟踪、围栏判定、告警管理）和数据层（配置文件、日志文件、图片存储）。系统的总体架构如图3-1所示。

**展示层**：基于HTML5 + Bootstrap 5 + Chart.js构建的深色主题Web界面，提供实时视频流显示、状态监控、历史查询和统计分析等功能。

**应用层**：基于Flask框架构建的Web服务，负责HTTP路由分发、API接口提供、模板渲染和视频流推送。

**业务逻辑层**：
- 检测模块（Detector）：封装YOLOv8模型，提供目标检测和跟踪功能
- 围栏模块（VirtualFence）：实现多边形围栏的构建和闯入判定
- 告警模块（AlertManager）：管理抓拍图片保存和日志记录
- 配置模块（ConfigManager）：管理系统配置的加载、保存和更新
- 统计模块（StatisticsManager）：提供数据统计和分析功能
- 历史管理模块（CaptureHistoryManager）：提供历史记录的搜索和管理功能

**数据层**：
- 模型文件：YOLOv8预训练权重文件
- 配置文件：settings.json和roi_config.json
- 日志文件：intrusion_history.csv
- 图片文件：抓拍的闯入图片

### 3.2 系统工作流程

系统的工作流程如下：

1. **初始化阶段**：加载配置文件，初始化检测器、围栏、告警管理器等组件，启动后台监控线程。
2. **视频读取阶段**：后台线程从视频源逐帧读取视频。
3. **目标检测阶段**：对每一帧执行YOLOv8目标检测，过滤出猫和狗类别，同时执行ByteTrack多目标跟踪。
4. **围栏判定阶段**：计算每个检测目标的落脚点（底部中心点），判断点是否在多边形围栏内部。
5. **告警触发阶段**：对于闯入禁区的目标，异步保存当前帧图片并记录日志。
6. **状态更新阶段**：更新闯入计数、系统状态和FPS等信息。
7. **帧推送阶段**：将标注后的帧通过共享缓冲区传递给HTTP流推送线程，最终在Web前端显示。

### 3.3 系统模块设计

#### 3.3.1 检测模块设计

检测模块（PetDetector）封装了YOLOv8模型的加载和推理逻辑。采用YOLOv8s版本作为默认模型，在COCO数据集上预训练，仅保留猫（类别15）和狗（类别16）两个类别的检测结果。检测时输入图像尺寸为640×640，采用ByteTrack跟踪器实现帧间目标关联。

#### 3.3.2 围栏模块设计

围栏模块（VirtualFence）使用多边形坐标数组构建虚拟围栏。OpenCV提供的`pointPolygonTest`函数用于判断点是否在多边形内部。围栏绘制时采用半透明填充效果，正常情况下显示为绿色，闯入时变为红色并闪烁。

#### 3.3.3 告警模块设计

告警模块（AlertManager）采用生产者-消费者模式设计异步日志处理器（AsyncAlertLogger）。主线程将抓拍任务（帧数据、文件路径、CSV记录行）放入有界队列，后台工作线程从队列中取出任务并顺序执行图片保存和日志写入。该设计确保了IO操作不会阻塞视频处理主线程。

#### 3.3.4 配置模块设计

配置模块（ConfigManager）支持点分键路径（如"detection.confidence_threshold"）的读写操作，方便上层代码获取和设置嵌套配置。配置以JSON格式持久化存储，支持运行时热更新。

### 3.4 技术选型

本系统的技术选型综合考虑了性能、开发效率和生态成熟度等因素：

| 技术组件 | 选型方案 | 选择理由 |
|---------|---------|---------|
| 目标检测 | YOLOv8s (Ultralytics) | 检测精度与推理速度的良好平衡 |
| 目标跟踪 | ByteTrack | 优秀的ID保持能力 |
| Web框架 | Flask | 轻量灵活，适合中小型应用 |
| 计算机视觉库 | OpenCV | 功能全面，社区成熟 |
| 前端框架 | Bootstrap 5 + Chart.js | 响应式设计，数据可视化 |
| 数据持久化 | JSON + CSV | 轻量级，无需数据库 |
| 配置管理 | YAML/JSON | 易读易写，支持嵌套结构 |

---

## 第四章 系统实现

### 4.1 环境搭建与配置管理

#### 4.1.1 开发环境

本系统的开发环境如下：

- 操作系统：Windows 11
- 编程语言：Python 3.9+
- 主要依赖：ultralytics, opencv-python, flask, numpy, pandas, PyYAML, PyQt6

#### 4.1.2 配置管理器实现

配置管理器（ConfigManager）实现了配置的加载、保存和层级读写功能。其核心设计如下：

```python
class ConfigManager:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = self.load_config()

    def get(self, key: str, default=None):
        keys = key.split('.')  # 如 "detection.confidence_threshold"
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
```

该设计支持通过点分路径语法方便地获取嵌套配置，如`config_manager.get('detection.confidence_threshold')`，提高了代码的可读性和可维护性。

### 4.2 目标检测与跟踪模块

#### 4.2.1 YOLOv8目标检测

系统使用Ultralytics框架加载预训练的YOLOv8s模型，在推理时通过`classes=[15, 16]`参数仅保留猫和狗两类检测结果，提高了检测效率和准确性。

```python
class PetDetector:
    def __init__(self, model_path='models/yolov8s.pt'):
        self.model = YOLO(model_path)

    def track(self, frame, conf=0.3):
        results = self.model.track(
            frame, imgsz=640, persist=True, conf=conf,
            classes=[15, 16],
            tracker="bytetrack.yaml", verbose=False
        )
        return results[0]
```

#### 4.2.2 ByteTrack多目标跟踪

ByteTrack跟踪器通过`persist=True`参数保持帧间的ID一致性。每个检测到的目标被分配唯一的track_id，使得系统能够区分不同的宠物个体，避免重复告警。

#### 4.2.3 类别平滑处理

在主处理循环中，系统实现了类别平滑缓冲机制。每个跟踪目标维护一个长度为10的类别历史队列，通过投票机制选择出现次数最多的类别作为稳定类别输出，有效避免了因单帧误检导致的类别跳变问题：

```python
id_class_history[tid] = deque(maxlen=10)
id_class_history[tid].append(cid)
stable_cls = Counter(id_class_history[tid]).most_common(1)[0][0]
label_name = "Cat" if stable_cls == 15 else "Dog"
```

### 4.3 虚拟围栏模块

#### 4.3.1 围栏构建

虚拟围栏由用户在多边形坐标数组定义，存储在`roi_config.json`配置文件中。系统启动时加载围栏坐标并构建多边形。

#### 4.3.2 闯入判定

系统使用OpenCV的`pointPolygonTest`函数进行几何判定。选择检测框的底部中心点作为目标的落脚点（foot_point），若该点在多边形内部或边界上，则判定为目标闯入禁入区域：

```python
foot_point = (int((box[0] + box[2]) / 2), int(box[3]))
if fence.is_intruding(foot_point):
    # 触发告警
```

#### 4.3.3 围栏可视化

围栏的绘制包括多边形的边缘线条和半透明填充。在安全状态下围栏显示为绿色，在闯入状态下变为红色并伴有闪烁动画效果：

```python
def draw_fence(self, frame, is_alert=False):
    color = (0, 0, 255) if is_alert else (0, 255, 0)
    cv2.polylines(frame, [self.polygon], isClosed=True, color=color, thickness=2)
    overlay = frame.copy()
    cv2.fillPoly(overlay, [self.polygon], color)
    return cv2.addWeighted(overlay, 0.3, frame, 0.7, 0)
```

### 4.4 异步告警模块

#### 4.4.1 异步日志记录器

告警模块的核心设计是AsyncAlertLogger，它采用生产者-消费者模式，使用线程安全的Queue实现异步IO操作：

```python
class AsyncAlertLogger:
    def __init__(self, log_file, max_queue_size=20):
        self.queue = queue.Queue(maxsize=max_queue_size)
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

    def _worker(self):
        while self.running:
            try:
                task = self.queue.get(timeout=1)
                if task is None:  # 停止信号
                    break
                frame, filepath, csv_row = task
                cv2.imwrite(filepath, frame)
                if csv_row:
                    with open(self.log_file, 'a', newline='', encoding='utf-8') as f:
                        csv.writer(f).writerow(csv_row)
                self.queue.task_done()
            except queue.Empty:
                continue
```

该设计的主要优势在于：主线程只需将任务放入队列即可返回，图片的编码、写入磁盘和日志记录等IO密集型操作均在后台线程中异步完成，从根本上消除了IO阻塞对视频处理帧率的影响。

#### 4.4.2 抓拍频率控制

为平衡告警响应速度和存储资源消耗，系统实施了抓拍频率控制。对于同一跟踪ID的目标，两次抓拍之间的最小间隔为5秒：

```python
if tid not in last_seen_time or (time.time() - last_seen_time[tid] > 5):
    alert_mgr.capture_intrusion_alert(annotated_frame, tid)
    last_seen_time[tid] = time.time()
```

### 4.5 视频流与Web服务

#### 4.5.1 双线程视频流架构

系统的视频处理采用双线程架构设计：

1. **监控线程**：主循环，负责视频帧读取、目标检测和跟踪、围栏判定、告警触发。处理后的标注帧写入共享缓冲区。
2. **HTTP流线程**：从共享缓冲区读取最新帧，编码为JPEG格式后通过multipart/x-mixed-replace协议逐帧推送到Web前端。

两个线程通过`threading.Lock`实现帧缓冲区的线程安全访问。这种设计实现了视频处理与HTTP推送的职责分离，提高了系统的并发处理能力。

```python
# 监控线程写入
with frame_buffer_lock:
    latest_annotated_frame = annotated_frame

# HTTP流线程读取
with frame_buffer_lock:
    if latest_annotated_frame is not None:
        ret, buffer = cv2.imencode('.jpg', latest_annotated_frame)
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
```

#### 4.5.2 RESTful API接口

系统提供了完整的RESTful API接口，支持前端与后端的数据交互：

| API端点 | 方法 | 功能描述 |
|---------|------|---------|
| `/video_feed` | GET | 实时视频流推送 |
| `/get_status` | GET | 获取当前系统状态 |
| `/get_history` | GET | 获取闯入历史（分页） |
| `/get_statistics` | GET | 获取统计数据 |
| `/api/config` | GET/POST | 获取/更新系统配置 |
| `/api/delete_capture` | POST | 删除抓拍记录 |
| `/api/search_captures` | POST | 搜索抓拍记录 |
| `/api/system_status` | GET | 获取系统运行状态 |

### 4.6 数据统计与管理

#### 4.6.1 统计分析

StatisticsManager基于Pandas DataFrame进行数据分析，提供了以下统计功能：

- **每日统计**：以天为单位统计闯入事件数量，默认展示最近7天的数据
- **小时模式**：统计24小时内各小时的闯入事件分布，识别高发时段
- **Top闯入者**：按跟踪ID统计闯入次数，识别频繁闯入的宠物
- **总体统计**：统计总事件数、唯一宠物数、首次和末次事件时间

#### 4.6.2 历史记录管理

CaptureHistoryManager提供了完整的CRUD操作，支持记录的搜索、删除和管理。搜索功能支持多条件组合过滤（日期范围、宠物ID、关键词），结果限制为最近的50条记录以防止页面过载。

### 4.7 Web前端实现

#### 4.7.1 实时监控页面

监控主页面采用深色主题设计，布局分为视频显示区和状态信息区。视频区域实时显示带标注的视频流（含检测框和围栏）。状态信息区展示当前系统状态、闯入计数、FPS等实时数据。

前端通过JavaScript定时轮询后端API，实现了以下动态效果：
- 每秒刷新系统状态（闯入计数、FPS）
- 闯入发生时警报标签闪烁（红色告警动画）
- 自动刷新历史记录列表
- 实时时钟显示

#### 4.7.2 抓拍历史管理页面

历史管理页面提供完整的记录管理和数据可视化功能。页面包含：
- 筛选搜索工具栏（日期范围、宠物ID、关键词）
- 统计摘要卡片（总抓拍数、唯一宠物数、今日抓拍数）
- 四个统计图表（每日闯入趋势、小时模式分布、Top闯入者、数据分布）
- 分页表格展示抓拍记录
- 图片在线查看模态框

统计图表使用Chart.js实现，包括折线图、柱状图、环形图和饼图四种类型。

### 4.8 系统服务化

#### 4.8.1 守护进程

system_service.py实现了系统的守护进程化管理，支持Web版和桌面版两种运行模式。服务进程具有以下能力：
- 后台启动子系统进程
- 监控子进程运行状态，异常退出时自动重启
- 优雅的信号处理和资源清理
- 日志记录（同时输出到文件和标准输出）

#### 4.8.2 启动脚本

start.bat提供了Windows平台下的便捷启动脚本，支持`start`、`desktop`、`stop`、`restart`、`service`等多种运行模式。

---

## 第五章 系统测试与分析

### 5.1 功能测试

#### 5.1.1 目标检测功能测试

系统在测试视频流上进行了目标检测功能测试。测试视频包含不同光照条件下猫和狗的活动场景。测试结果表明：

- 系统能够稳定检测视频中的猫和狗目标
- 在正脸和侧脸角度下检测准确率较高
- 对于部分遮挡情况（如宠物被家具部分遮挡），系统仍能维持检测

#### 5.1.2 目标跟踪功能测试

ByteTrack跟踪器在测试中的表现：
- 在简单场景下ID保持稳定，未出现ID跳变
- 在多目标场景下，各目标的跟踪ID保持独立
- 当目标暂时离开画面后重新出现时，系统会分配新的ID

#### 5.1.3 虚拟围栏功能测试

围栏判定功能的测试结果：
- 多边形区域边界判定准确
- 闯入检测延迟小于1帧
- 围栏颜色变化响应及时
- 半透明填充效果清晰可辨

#### 5.1.4 异步告警功能测试

对异步告警模块的测试包括：
- 抓拍图片能够成功保存到指定目录
- CSV日志记录完整，包含时间、ID、文件名等信息
- 多次连续闯入场景下，抓拍间隔控制有效（不小于5秒）
- 异步队列在满载时丢弃任务而非阻塞主线程
- 后台IO操作未明显影响视频处理帧率

#### 5.1.5 Web功能测试

Web界面各功能模块的测试结果：
- 视频流推送正常，延迟在可接受范围内
- 状态信息实时更新
- 历史记录分页查询正常
- 搜索和筛选功能准确
- 图片查看和删除功能可用
- 配置读取和保存功能正常
- 数据导出功能正常

### 5.2 性能测试

#### 5.2.1 视频处理帧率

在配置为Intel Core i7、16GB RAM、NVIDIA GPU的环境下，对系统进行帧率测试：

| 测试场景 | 平均FPS | 说明 |
|---------|---------|------|
| 无目标场景 | 28-32 | 仅有背景画面 |
| 单目标场景 | 24-28 | 一个检测目标 |
| 多目标场景 | 20-25 | 2-3个检测目标 |

测试结果表明系统能够维持在20 FPS以上的处理速度，满足实时监控的需求。

#### 5.2.2 异步IO性能

对比同步保存和异步保存两种方式对视频帧率的影响：

| 保存方式 | 平均FPS | 帧率波动 |
|---------|---------|---------|
| 同步保存 | 15-18 | 大幅波动（卡顿明显） |
| 异步保存 | 24-28 | 稳定（无明显卡顿） |

异步保存机制在图像写入磁盘期间将帧率提升了约60%，且消除了帧率波动，显著改善了用户体验。

### 5.3 系统优缺点分析

#### 5.3.1 系统优势

1. **检测精度高**：基于YOLOv8s预训练模型，在COCO数据集上经过充分训练，对猫和狗两类目标具有良好的检测能力。
2. **实时性好**：通过异步IO和双线程架构设计，系统能够维持20 FPS以上的处理速度。
3. **部署简单**：基于Python和轻量级依赖，无需复杂的数据库配置，开箱即用。
4. **交互性强**：Web界面提供完整的监控、查询、管理和配置功能。
5. **可扩展性好**：模块化设计便于功能扩展和模型替换。

#### 5.3.2 系统不足与改进方向

1. **模型泛化能力**：YOLOv8s模型在特定品种或特定角度下的检测精度仍有提升空间，可通过微调或使用更高级的模型版本改进。
2. **多摄像头支持**：当前版本仅支持单路视频源，可扩展为支持多摄像头的分布式监控架构。
3. **移动端适配**：Web界面在移动端的体验有待优化，可开发专门的移动应用。
4. **智能分析**：可进一步引入行为分析功能，识别宠物的异常行为模式。

---

## 第六章 总结与展望

### 6.1 工作总结

本文针对家庭宠物安全防护的需求，设计并实现了一套基于计算机视觉的宠物智能安防监控系统PetGuard。系统基于YOLOv8s目标检测算法和ByteTrack多目标跟踪技术，结合虚拟围栏和异步告警机制，实现了对宠物闯入禁入区域的实时检测和告警。

主要工作成果包括：

1. **技术实现层面**：成功将YOLOv8目标检测、ByteTrack多目标跟踪、虚拟围栏判定、异步IO处理等多项技术集成到一个完整的安防监控系统中，验证了各项技术在实际场景中的可行性。

2. **系统架构层面**：采用双线程视频处理架构和生产者-消费者异步日志模型，在保证系统实时性的同时，确保了IO操作的可靠性。

3. **用户体验层面**：基于Flask和Bootstrap构建了深色主题的Web监控后台，提供了视频流、状态展示、历史查询、统计分析等完整的交互功能。

4. **工程实践层面**：实现了配置管理、数据管理、守护进程、启动脚本等完整的工程化配套设施，提升了系统的可用性和可维护性。

### 6.2 未来展望

随着计算机视觉技术的不断发展，本系统在以下方面仍有进一步优化和扩展的空间：

1. **模型优化**：采用更轻量化的模型（如YOLOv8n）提升在边缘设备上的运行效率，或使用YOLOv8m/x提升检测精度。

2. **多模态分析**：引入音频分析能力，通过宠物叫声识别宠物的情绪状态，实现更全面的监护。

3. **云端协同**：将视频处理和AI推理迁移到云端，实现本地采集、云端分析的分布式架构，支持远程访问和跨设备同步。

4. **深度学习定制**：收集特定场景下的宠物数据进行模型微调，提升在特定监控环境下的检测精度。

5. **隐私保护**：引入视频数据加密和匿名化处理机制，保护家庭隐私安全。

---

## 参考文献

[1] Ultralytics. YOLOv8: A State-of-the-Art Object Detection Model [EB/OL]. https://github.com/ultralytics/ultralytics, 2024.

[2] Zhang Y, Sun P, Jiang Y, et al. ByteTrack: Multi-Object Tracking by Associating Every Detection Box [C]. European Conference on Computer Vision (ECCV), 2022.

[3] Redmon J, Divvala S, Girshick R, et al. You Only Look Once: Unified, Real-Time Object Detection [C]. IEEE Conference on Computer Vision and Pattern Recognition (CVPR), 2016.

[4] Bewley A, Ge Z, Ott L, et al. Simple Online and Realtime Tracking [C]. IEEE International Conference on Image Processing (ICIP), 2016.

[5] Lin T Y, Maire M, Belongie S, et al. Microsoft COCO: Common Objects in Context [C]. European Conference on Computer Vision (ECCV), 2014.

[6] Bradski G. The OpenCV Library [J]. Dr. Dobb's Journal of Software Tools, 2000.

[7] Grinberg M. Flask Web Development: Developing Web Applications with Python [M]. O'Reilly Media, 2018.

[8] 刘明, 张华. 基于改进YOLOv5的社区智能安防监控系统设计 [J]. 计算机工程与应用, 2023, 59(15): 236-245.

[9] 王磊, 陈静. 基于深度学习的宠物行为识别系统研究 [J]. 计算机应用与软件, 2024, 41(3): 178-184.

[10] 赵伟, 李明. 基于深度学习的视频监控目标检测技术综述 [J]. 自动化学报, 2023, 49(7): 1411-1430.

[11] Jocher G, Chaurasia A, et al. YOLOv5 by Ultralytics [EB/OL]. https://github.com/ultralytics/yolov5, 2021.

[12] Paszke A, Gross S, Massa F, et al. PyTorch: An Imperative Style, High-Performance Deep Learning Library [C]. Advances in Neural Information Processing Systems (NeurIPS), 2019.

[13] Perez L, Wang J. The Effectiveness of Data Augmentation in Image Classification using Deep Learning [J]. arXiv preprint arXiv:1712.04621, 2017.

[14] Wojke N, Bewley A, Paulus D. Simple Online and Realtime Tracking with a Deep Association Metric [C]. IEEE International Conference on Image Processing (ICIP), 2017.

[15] 周志华. 机器学习 [M]. 北京: 清华大学出版社, 2016.

---

## 附录

### 附录A：系统运行界面

- 图A-1：系统监控主界面
- 图A-2：历史记录管理页面
- 图A-3：数据统计分析页面

### 附录B：配置文件说明

**config/roi_config.json**
```json
{
    "polygon": [[298, 141], [1093, 169], [1094, 608], [269, 599]],
    "target_classes": [15, 16],
    "conf_threshold": 0.15
}
```

**config/settings.json**（运行时生成）
```json
{
    "detection": {
        "model_path": "models/yolov8s.pt",
        "confidence_threshold": 0.4,
        "classes": [15, 16],
        "image_size": 640
    },
    "fence": {
        "polygon": [...],
        "enable_fencing": true
    },
    "storage": { ... },
    "performance": { ... },
    "ui": {
        "web_port": 5000,
        "web_host": "0.0.0.0"
    }
}
```

### 附录C：核心类图

- **PetDetector**：封装YOLOv8模型的检测和跟踪
- **VirtualFence**：多边形虚拟围栏的构建和判定
- **AlertManager**：告警管理和异步日志记录
- **AsyncAlertLogger**：异步生产者-消费者队列处理器
- **ConfigManager**：层级配置的读写管理
- **StatisticsManager**：基于Pandas的数据统计分析
- **CaptureHistoryManager**：历史记录的CRUD操作和搜索
- **PetGuardService**：系统守护进程管理

---

*毕业论文全文完*

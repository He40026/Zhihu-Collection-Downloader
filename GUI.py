import sys
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QPushButton, QLabel, QMessageBox, QDesktopWidget,
                             QLineEdit, QHBoxLayout, QSpacerItem, QSizePolicy)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from Main import all_main

class DownloadThread(QThread):
    """下载线程类"""
    finished = pyqtSignal()  # 下载完成信号
    error = pyqtSignal(str)  # 错误信号
    
    def run(self):
        """线程执行函数"""
        try:
            all_main()
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class ZhihuDownloaderGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("知乎收藏夹下载器")
        self.resize(500, 350)  # 增加窗口宽度和高度以提供更多空间
        
        # 将窗口居中显示
        self.center()
        
        # 创建主部件和布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setAlignment(Qt.AlignCenter)
        main_layout.setSpacing(15)  # 设置整体垂直间距
        
        # 添加标题
        title_label = QLabel("知乎收藏夹下载器")
        title_label.setStyleSheet("""
            font-size: 22px; 
            font-weight: bold; 
            margin-bottom: 25px;
            color: #333;
        """)
                # 添加垂直间距
        main_layout.addSpacing(30)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 添加URL输入框和保存按钮
        url_layout = QHBoxLayout()
        url_layout.setSpacing(10)  # 设置水平间距
        url_label = QLabel("收藏夹URL:")
        url_label.setStyleSheet("font-size: 14px;")
        self.url_input = QLineEdit()
        self.url_input.setStyleSheet("""
            padding: 8px;
            font-size: 14px;
            min-width: 250px;
        """)
        self.url_input.setPlaceholderText("请输入知乎收藏夹网址")
        url_save_btn = QPushButton("保存URL")
        url_save_btn.setStyleSheet("""
            padding: 8px 15px;
            font-size: 14px;
            background-color: #5B9BD5;
            color: white;
            border-radius: 4px;
        """)
        url_save_btn.clicked.connect(self.save_url)
        
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(url_save_btn)
        main_layout.addLayout(url_layout)
        
        # 添加垂直间距
        main_layout.addSpacing(20)
        
        # 添加保存路径输入框和保存按钮
        path_layout = QHBoxLayout()
        path_layout.setSpacing(10)
        path_label = QLabel("保存路径:")
        path_label.setStyleSheet("font-size: 14px;")
        self.path_input = QLineEdit()
        self.path_input.setStyleSheet("""
            padding: 8px;
            font-size: 14px;
            min-width: 250px;
        """)
        self.path_input.setPlaceholderText("请输入文件保存路径")
        path_save_btn = QPushButton("保存路径")
        path_save_btn.setStyleSheet("""
            padding: 8px 15px;
            font-size: 14px;
            background-color: #5B9BD5;
            color: white;
            border-radius: 4px;
        """)
        path_save_btn.clicked.connect(self.save_path)
        
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(path_save_btn)
        main_layout.addLayout(path_layout)
        
        # 添加较大的垂直间距
        main_layout.addSpacing(25)
        
        # 加载已保存的设置
        self.load_saved_settings()
        
        # 下载按钮
        self.download_btn = QPushButton("开始下载")
        self.download_btn.setStyleSheet("""
            font-size: 16px; 
            padding: 12px 25px; 
            background-color: #4CAF50; 
            color: white;
            border-radius: 6px;
        """)
        self.download_btn.clicked.connect(self.start_download)
        main_layout.addWidget(self.download_btn, alignment=Qt.AlignCenter)
        
        # 添加垂直间距
        main_layout.addSpacing(1)
        
        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            color: #666; 
            font-style: italic; 
            font-size: 14px;
            margin-top: 10px;
        """)
        main_layout.addWidget(self.status_label)
        
        # # 添加弹性空间
        # main_layout.addStretch(1)
        
        # 添加作者信息
        author_label = QLabel("鸿博出品")
        author_label.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        author_label.setStyleSheet("""
            color: #999; 
            font-size: 12px; 
            margin-top: 0px;
        """)
        main_layout.addWidget(author_label)
        
        # 初始化下载线程
        self.download_thread = None
        # 保存当前使用的URL和路径
        self.current_url = ""
        self.current_path = ""
    
    def center(self):
        """将窗口居中显示"""
        # 获取屏幕的几何信息
        screen = QDesktopWidget().screenGeometry()
        # 获取窗口的几何信息
        size = self.geometry()
        # 计算窗口左上角的新位置
        new_left = (screen.width() - size.width()) // 2
        new_top = (screen.height() - size.height()) // 2
        # 移动窗口到新位置
        self.move(new_left, new_top)
    
    def load_saved_settings(self):
        """加载已保存的设置"""
        try:
            with open("url.json", "r", encoding="utf-8") as f:
                url_data = json.load(f)
                if url_data.get("collections") and len(url_data["collections"]) > 0:
                    self.url_input.setText(url_data["collections"][0].get("url", ""))
                    self.path_input.setText(url_data["collections"][0].get("path", ""))
                    self.current_url = url_data["collections"][0].get("url", "")
                    self.current_path = url_data["collections"][0].get("path", "")
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    
    def save_url(self):
        """保存URL到配置文件"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "警告", "请输入有效的收藏夹URL")
            return
        
        try:
            # 尝试加载现有配置
            try:
                with open("url.json", "r", encoding="utf-8") as f:
                    url_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                url_data = {"collections": []}
            
            # 获取当前路径（如果存在）
            current_path = ""
            if len(url_data["collections"]) > 0:
                current_path = url_data["collections"][0].get("path", "")
            
            # 更新或添加URL
            if len(url_data["collections"]) > 0:
                url_data["collections"][0]["url"] = url
            else:
                url_data["collections"].append({"url": url, "path": current_path})
            
            with open("url.json", "w", encoding="utf-8") as f:
                json.dump(url_data, f, ensure_ascii=False, indent=2)
            
            # 更新当前使用的URL
            self.current_url = url
            QMessageBox.information(self, "成功", "URL保存成功")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存URL时出错:\n{str(e)}")
    
    def save_path(self):
        """保存路径到配置文件"""
        path = self.path_input.text().strip()
        
        try:
            # 尝试加载现有配置
            try:
                with open("url.json", "r", encoding="utf-8") as f:
                    url_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                url_data = {"collections": []}
            
            # 获取当前URL（如果存在）
            current_url = ""
            if len(url_data["collections"]) > 0:
                current_url = url_data["collections"][0].get("url", "")
            
            # 更新或添加路径
            if len(url_data["collections"]) > 0:
                url_data["collections"][0]["path"] = path
            else:
                url_data["collections"].append({"url": current_url, "path": path})
            
            with open("url.json", "w", encoding="utf-8") as f:
                json.dump(url_data, f, ensure_ascii=False, indent=2)
            
            # 更新当前使用的路径
            self.current_path = path
            QMessageBox.information(self, "成功", "路径保存成功")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存路径时出错:\n{str(e)}")
    
    def start_download(self):
        """启动下载过程"""
        # 检查URL是否已保存
        if not self.current_url:
            QMessageBox.warning(self, "警告", "请先输入并保存收藏夹URL")
            return
        
        # 禁用按钮
        self.download_btn.setEnabled(False)
        self.status_label.setText("开始下载...")
        
        # 如果已有下载线程在运行，先等待它完成
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.quit()
            self.download_thread.wait()
        
        # 创建并启动新的下载线程
        self.download_thread = DownloadThread()
        self.download_thread.finished.connect(self.on_download_finished)
        self.download_thread.error.connect(self.on_download_error)
        self.download_thread.start()
    
    def on_download_finished(self):
        """下载完成处理"""
        self.status_label.setText("下载完成！")
        self.download_btn.setEnabled(True)
        QMessageBox.information(self, "完成", "下载任务已完成！")
    
    def on_download_error(self, error_msg):
        """下载错误处理"""
        self.status_label.setText(f"下载失败: {error_msg}")
        self.download_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", f"下载过程中出错:\n{error_msg}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 使用 Fusion 样式，看起来更现代
    
    # 设置应用样式
    app.setStyleSheet("""
        QWidget {
            font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
            background-color: #f5f5f5;
        }
        QPushButton {
            min-width: 80px;
        }
        QPushButton:hover {
            background-color: #e0e0e0;
        }
        QLineEdit {
            min-height: 30px;
        }
        QMessageBox {
            min-width: 300px;
        }
    """)
    
    window = ZhihuDownloaderGUI()
    window.show()
    sys.exit(app.exec_())
from PyQt5.QtWidgets import QApplication, QTreeView,  QVBoxLayout, QWidget
from PyQt5.QtCore import pyqtSignal, QModelIndex, QThread, QCoreApplication
from PyQt5.QtGui import QStandardItemModel, QStandardItem

import time

class DataLoadingThread(QThread):
    data_loaded_signal = pyqtSignal(list)

    def __init__(self, data_count, parent=None):
        # 调用父类（DataLoadingThread的父类）的构造函数，传入parent参数
        super(DataLoadingThread, self).__init__(parent)
        # 将传入的data_count参数赋值给类的实例变量self.data_count
        self.data_count = data_count

    def run(self):
        # 模拟数据加载
        data = [f"Item {i}" for i in range(self.data_count)]
        self.data_loaded_signal.emit(data)

class MainWindow(QWidget):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.model = QStandardItemModel(0, 1)  # 动态确定行数，1列
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.model)
        layout = QVBoxLayout()
        layout.addWidget(self.tree_view)
        self.setLayout(layout)
        self.thread = DataLoadingThread(100000)  # 加载10000行
        self.thread.data_loaded_signal.connect(self.on_data_loaded)
        self.thread.start()

    def on_data_loaded(self, data):
        a = time.perf_counter()
        self.model.beginInsertRows(QModelIndex(), 0, len(data) - 1)
        for i, item_data in enumerate(data):
            self.model.appendRow(QStandardItem(item_data))
            
        self.model.endInsertRows()
        self.thread.terminate()
        b = time.perf_counter()
        print(f'cost time: {b-a}')

app = QApplication([])
window = MainWindow()
window.show()
app.exec_()
import sys
from PyQt5.QtGui import QCloseEvent, QIcon, QDrag, QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,\
    QHBoxLayout, QWidget, QTreeView, QLabel, QLineEdit, QPushButton, QFileDialog, QVBoxLayout
from PyQt5.QtCore import QMimeData, Qt, QModelIndex, QThread, QCoreApplication
import paramiko
import re, os, stat
import logging, loguru
import pytest
import time
import asyncio

# logging.basicConfig(level = logging.DEBUG, format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)

logger = loguru.logger


class FileInfo:
    def __init__(self, description):
        self.description = description
        self.parse_description()
    
    def parse_description(self):
        pattern = re.compile(
            r'(?P<permissions>[drwx\-@+.]+)\s+'
            r'(?P<links>\d+)\s+'
            r'(?P<owner>\w+)\s+'
            r'(?P<group>\w+)\s+'
            r'(?P<size>[\d\.]+[BKMG]?)\s+'
            r'(?P<month>\w+)\s+'
            r'(?P<day>\d+)\s+'
            r'(?P<time>[\d:]+)\s+'
            r'(?P<name>.+)'
        )
        match = pattern.match(self.description)
        if match:
            self.permissions = match.group('permissions')
            self.links = int(match.group('links'))
            self.owner = match.group('owner')
            self.group = match.group('group')
            self.size = match.group('size')
            self.last_modified = f"{match.group('month')} {match.group('day')} {match.group('time')}"
            self.name = match.group('name')
            # self.isdir = True if self.permissions[0] == 'd' else False 
            if self.permissions[0] == 'd':
                self.file_type = 'folder'
            else:
                self.file_type = self.name.split('.')[-1] if '.' in self.name else ''
        else:
            raise ValueError('Invalid file description format')
    
    def __str__(self):
        return f"{self.permissions} {self.links} {self.owner} {self.group} {self.size} {self.last_modified} {self.name}"


# 使用单例模式来进行设计
class Executor:
    _instance = None
    def __init__(self, hostname, port, username, password):
        _instance = None
        self.hostname = hostname
        self.port = port 
        self.username = username
        self.password = password
        self.ssh = None
        self.sftp = None
       
    @classmethod
    def get_instance(cls, hostname, port, username, password):
        if cls._instance is None:
            cls._instance = cls(hostname, port, username, password)
            try:
                cls._instance.connect() # 连接
            except Exception as e:
                print(e)
        return cls._instance
    
    def connect(self):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(self.hostname,
                         self.port,
                         self.username,
                         self.password
                         )
        self.sftp = self.ssh.open_sftp()

    def disconnect(self):
        if self.ssh:
            self.ssh.close()
        
    # def download(self, remote_path, local_path):
    #     # self.sftp.get(remotepath = remote_path, localpath=local_path)
    #     command = f'get -r {remote_path} {local_path}'  # 文件和文件夹都可以用递归
    #     logger.debug(command)
    #     stdin, stdout, stderr = self.sftp.exec_command(command)
    #     logger.debug(stdout.read().decode())
    #     logger.debug(stderr.read().decode())
    #     logger.info('下载成功')
    
    
    # ref: https://blog.csdn.net/RayMand168/article/details/135463557
    def download(self, remote_path, local_path):  # eg: remote_path : /home/dir   local_path: /home/urahyou/  -> /home/urahyou/dir
        remote_file = self.sftp.stat(remote_path)
        if stat.S_ISDIR(remote_file.st_mode): # 如果是文件夹则要递归下载
            self.check_local_dir(local_path)
            logger.debug('开始下载文件夹：{}'.format(remote_path))
            for remote_file_name in self.sftp.listdir(remote_path):
                sub_remote_path = os.path.join(remote_path, remote_file_name)
                sub_local_path = os.path.join(local_path, remote_file_name)
                self.download(sub_remote_path, sub_local_path) # 递归下载
        else:
            # 已经到了文件就直接下载
            logger.debug('开始下载文件：{}'.format(remote_path))
            if self.check_local_file(local_path): 
                logger.debug(f'{local_path} 已经存在, 跳过:')
            else:
                logger.debug(f'remote_path: {remote_path}, local_path: {local_path}')
                self.sftp.get(remotepath = remote_path, localpath = local_path)
                
                
    def upload(self, local_path, remote_path):
        if os.path.isdir(local_path):
            self.check_remote_dir(remote_path)
            logger.debug('开始上传文件夹：{}'.format(local_path))
            for local_file in os.listdir(local_path):
                sub_remote_path = os.path.join(remote_path, local_file)
                sub_local_path = os.path.join(local_path, local_file)
                self.upload(sub_local_path, sub_remote_path) # 递归上传
        else:
            # 已经到了文件就直接上传
            logger.debug('开始上传文件：{}'.format(local_path))
            if self.check_remote_dir()
            logger.debug(f'localpath: {local_path}, remote_path: {remote_path}')
            self.sftp.put(localpath=local_path, remotepath=remote_path) 
            

    def check_remote_dir(self, remote_path):
        remote_file_name = remote_path.split('/')[-1]
        remote_path_parent = '/'.join(remote_path.split('/')[:-2])
        # 如果远程不存在目录则创建
        if remote_file_name not in self.sftp.listdir(remote_path_parent):
            self.sftp.mkdir(remote_path)
    
        
    def check_local_dir(self, local_path):
        if not os.path.exists(local_path):
            os.makedirs(local_path)
            
    def check_local_file(self, local_path):
        if os.path.exists(local_path):
            return True
        else:
            return False
        
    def check_remote_file(self, remote_path):
        return False
        
        
    # def upload(self, local_path, remote_path):
    #     print(f'local_path: {local_path}, remote_path: {remote_path}')
    #     self.sftp.put(localpath=local_path, remotepath=remote_path)
    #     logger.info('上传成功')
        
    def local_move(self, from_path, to_path):
        command = f"mv {from_path} {to_path}" # mv是不用加-r也可以移动文件夹的
        logger.debug(f'command: {command}')
        r = os.popen(command)
        output = r.read()
        r.close()
        return output
    
    def execute_command(self, command, type):
        output = None
        errors = None
        if type == "remote":
            if not self.ssh:
                raise Exception("SSH connection not established")
            # print('you are here')
            stdin, stdout, stderr = self.ssh.exec_command(command)
            output = stdout.read().decode()
            errors = stdout.read().decode()
        elif type == "local":
            # path = command.split(' ')[-1]
            # output = self.ls(path)
            # print(f'command: {command}')
            output = os.popen(command).read()
            # logger.debug(output)
        else:
            logger.error('type error! not a valid type (local, remote)')
           
        return output, errors
    
    def parse_ls_output(self, output):
        file_infos = []
        lines = output.split('\n')
        for line in lines:
            if line:
                try:
                    file_info = FileInfo(line)
                    file_infos.append(file_info)
                except ValueError:
                    # 忽略无效行
                    continue
        return file_infos
        

class Utils():
    # 在model里面按照index获取path
    @staticmethod
    def get_path_from_index(root_path, model:QStandardItemModel, index:QModelIndex):
        if not index.isValid():
            return 
        if index.row() != 0: 
            index = index.sibling(index.row(), 0)
        full_path = model.itemFromIndex(index).text()
        parent_index = index.parent()
        
        while parent_index.isValid():
            parent_path = model.itemFromIndex(parent_index).text()
            full_path = os.path.join(parent_path, full_path)
            parent_index = parent_index.parent()
        full_path = os.path.join(root_path, full_path)
        return full_path
        
            
class FileTreeView(QTreeView):
    def __init__(self, root_path = '~',
                 loc = 'local',
                 parent = None
                 ):
        super(FileTreeView, self).__init__(parent)
        self.root_path = root_path
        self.loc = loc
        # 获取一个统一的单例
        self.executor = Executor.get_instance(hostname='', port=22, username='', password='')
        # 连接槽函数
        self.expanded.connect(self.onItemExpand)
        
        # 设置一些属性
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        
        self.fileIcon = QIcon('icons/file.png')
        self.folderIcon = QIcon('icons/folder.png')
        self.emptyFolderIcon = QIcon('icons/empty_folder.png')
        
    def onItemExpand(self, index):
        node = self.model().itemFromIndex(index)
        
        # 要先清空当前节点下面的所有子节点
        self.model().removeRows(0, node.rowCount(), index)
        
        cur_full_path = Utils.get_path_from_index(self.root_path, self.model(), index)
        # print(f'cur_full_path: {cur_full_path}')
        self.list_dir(cur_full_path,  node, loc=self.loc, depth=2)
        
    
    def list_dir(self, path, node, loc, depth):
        logger.debug(f'lisr_dir depth is {depth}')
        if depth == 0:
            print('return')
            return
        # node为根节点，列出node下面的两级目录
        a = time.perf_counter()
        output, errors = self.executor.execute_command(f'ls -alh {path}', loc)
        b = time.perf_counter()
        print(f'ls -alh {path} time: {b-a}')
        a = time.perf_counter()
        file_infos = self.executor.parse_ls_output(output)
        b = time.perf_counter()
        print(f'parse_ls_output time: {b-a}')
        
        if len(file_infos) <= 3: # 文件夹下面是空的
            node.setIcon(self.emptyFolderIcon) # 添加空文件夹标志
            
        a = time.perf_counter()
        # self.setUpdatesEnabled(False)
        for i, file_info in enumerate(file_infos[3:]):
            # print(file_info)
            self.add_file_info(path, node, file_info, loc, depth)
            if i % 100 == 99:
                QApplication.processEvents()
        # self.setUpdatesEnabled(True)
        b = time.perf_counter()
        print(f'add_file_info time: {b-a}')
                    
        
    def add_file_info(self, path, node, file_info, loc, depth):
        name = file_info.name
        size = file_info.size
        file_type = file_info.file_type
        nameItem = QStandardItem(name)
        nameItem.setEditable(False)
        typeItem = QStandardItem(file_type)
        typeItem.setEditable(False)
        if file_info.file_type == 'folder':
            sizeItem = QStandardItem('--') # 文件夹不显示大小
        else:
            sizeItem = QStandardItem(size)
        sizeItem.setEditable(False)
        node.appendRow([nameItem, typeItem, sizeItem])
        if file_info.file_type == 'folder':
            nameItem.setIcon(self.folderIcon)
            nameItem.appendRow(QStandardItem()) # 添加一个空的子节点
            # self.list_dir(path+'/'+file_info.name, nameItem, type, depth-1)
        else:
            nameItem.setIcon(self.fileIcon)
        
        

class MyTreeModel(QStandardItemModel):
    def __init__(self, root_path = '~', loc='local', parent=None):
        super().__init__(parent)
        self.root_path = root_path
        self.loc = loc
        # 获取一个统一的单例
        self.executor = Executor.get_instance(hostname='', port=22, username='', password='')
        
        self.setHorizontalHeaderLabels(['name', 'type', 'size'])

    def mimeTypes(self):
        return ['fileDesc']
    

    def columnData(self, index, row, column):
        return self.itemFromIndex(self.index(row, column, index.parent())).data()


    def mimeData(self, indexes):
        try:
            mime_data = QMimeData()
            send_message = {}
            for index in indexes: # 事实上只应该有一个
                # print(self.itemFromIndex(index).text())
                # print(index.row(), index.column())
                if index.isValid():
                    logger.debug('index is valid')
                    send_message['file_name'] = self.itemFromIndex(index).text()
            send_message['from_where'] = self.loc # 用来标识是从哪里来的
            send_message['full_path'] = Utils.get_path_from_index(root_path = self.root_path, 
                                                    model = self, 
                                                    index = indexes[0]) # 用来标识文件的完整路径
            # print('hello:', self.columnData(indexes[0], indexes[0].row(), 1))
            send_message = str(send_message).encode()
            mime_data.setData('fileDesc', send_message)
            # print(mime_data.data('fileDesc').data().decode())
        except Exception as e:
            logger.error(e)
            return None
        return mime_data
    
    def dropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: QModelIndex) -> bool:
        if not data.hasFormat('fileDesc'):
            logger.error('no fileDesc')
            return False
        if action == Qt.IgnoreAction:
            logger.debug('action is ignore')
            return False
        
        send_message = eval(data.data('fileDesc').data().decode()) # str --> dict
        # for key in send_message.keys():
        #     logger.debug(f'key: {key}, value: {send_message[key]}')
        from_path = send_message['full_path']
        to_path = Utils.get_path_from_index(root_path = self.root_path, model=self, index=parent) + '/' + send_message['file_name']
        # to_path = Utils.get_path_from_index(root_path = self.root_path, model=self, index=parent) + '/'

        from_loc = send_message['from_where']
        to_loc = self.loc
        
        
        # print(row, parent.row()) # 这两个不一样啊
        if self.itemFromIndex(parent.sibling(parent.row(), 1)).text() == 'folder':
            if from_loc == 'local' and to_loc == 'remote':
                self.executor.upload(from_path, to_path)
            if from_loc == 'local' and to_loc == 'local':
                self.executor.execute_command(f'cp -r {from_path} {to_path}', 'local')
            if from_loc == 'remote' and to_loc == 'local':
                self.executor.download(from_path, to_path)
            if from_loc == 'remote' and to_loc == 'remote':
                self.executor.execute_command(f'cp -r {from_path} {to_path}', 'remote')
        else:
            print('not a folder')
            return False
            
        return True
    
    def flags(self, index):
        if index.column() == 0:
            return Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
        else:
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled
                

class FileManager(QMainWindow):
    def __init__(self):
        super(FileManager, self).__init__()
        
        
        self.setWindowTitle('FileManager')
        self.resize(1024, 768)
        # 创建两个树视图
        local_root_path = '/Users/urahyou/git'
        remote_root_path = '/Users/urahyou/git'
        
        self.eidtLine1 = QLineEdit()
        self.eidtLine1.setText(local_root_path)
        self.eidtLine2 = QLineEdit()
        self.eidtLine2.setText(remote_root_path)
        
        self.tree_view1 = FileTreeView(root_path=local_root_path, loc='local')
        self.tree_model1 = MyTreeModel(root_path=self.tree_view1.root_path, loc='local')
        self.tree_view1.setModel(self.tree_model1)
        self.tree_view1.setColumnWidth(0, 200)
        # self.tree_view1.setColumnWidth(1, 100)
        # self.tree_view1.setColumnWidth(2, 100)
        
        self.tree_view2 = FileTreeView(root_path=remote_root_path, loc='remote')
        self.tree_model2 = MyTreeModel(root_path=self.tree_view2.root_path, loc='remote')
        self.tree_view2.setModel(self.tree_model2)
        self.tree_view2.setColumnWidth(0, 200)
        # self.tree_view2.setColumnWidth(1, 100)
        # self.tree_view2.setColumnWidth(2, 100)
        
        # executor = Executor(hostname=hostname, port=port, username=username, password=password)
            
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()
        
        left_layout.addWidget(self.eidtLine1)
        left_layout.addWidget(self.tree_view1)
        
        right_layout.addWidget(self.eidtLine2)
        right_layout.addWidget(self.tree_view2)
            
        layout = QHBoxLayout()
        layout.addLayout(left_layout)
        layout.addLayout(right_layout)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        
        self.tree_view1.list_dir(local_root_path, self.tree_model1, 'local', 2)
        self.tree_view2.list_dir(remote_root_path, self.tree_model2, 'remote', 2)
        

if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    file_manager = FileManager()
    file_manager.show()
    sys.exit(app.exec())
    
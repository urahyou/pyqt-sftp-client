import sys
from PyQt5.QtGui import QCloseEvent, QIcon, QDrag, QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,\
    QHBoxLayout, QWidget, QTreeView
from PyQt5.QtCore import QMimeData, Qt
import paramiko
import re, os
import logging


logging.basicConfig(level = logging.DEBUG, format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FileInfo:
    def __init__(self, description):
        self.description = description
        self._parse_description()
        
    def _parse_description(self):
        pattern = re.compile(
            r'(?P<permissions>[drwx\-@+]+)\s+'
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
            self.isdir = True if self.permissions[0] == 'd' else False # 判断是否为文件夹
            self.file_type = self.name.split('.')[-1] if '.' in self.name else ''
            if self.isdir:
                self.file_type = 'folder'
        else:
            raise ValueError('Invalid file description format')
        
    def __str__(self):
        return f"{self.permissions} {self.links} {self.owner} {self.group} {self.size} {self.last_modified} {self.name}"


class CommandExecutor:
    def __init__(self, hostname, port, username, password):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        # self.ls = sh.ls.bake('-alh')
        self.ssh = None
        self.sftp = None
        
    
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
        
    def download(self, remote_path, local_path):
        self.sftp.get(remotepath = remote_path, localpath=local_path)
        logger.info('下载成功')
        
        
    def upload(self, local_path, remote_path):
        self.sftp.put(localpath=local_path, remotepath=remote_path)
        logger.info('上传成功')
        
    def local_move(self, from_path, to_path):
        command = f"mv {from_path} {to_path}"
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
            
            stdin, stdout, stderr = self.ssh.exec_command(command)
            output = stdout.read().decode()
            errors = stdout.read().decode()
        elif type == "local":
            # path = command.split(' ')[-1]
            # output = self.ls(path)
            output = os.popen(command).read()
            logger.debug(output)
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


class DraggableTreeView(QTreeView):
    def __init__(self, root_path = '~', executor = None, type='local', parent=None):
        super(DraggableTreeView, self).__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True) # 显示一个指示器，也就是提示会拖放到哪里
        # self.clicked.connect(self.onItemClicked)
        self.expanded.connect(self.onItemExpand)
        self.root_path = root_path
        self.executor = executor
        self.type = type
        
    # def startDrag(self, supportedActions):
    #     # 返回被选中的一系列index的列表
    #     indexes = self.selectedIndexes() # 返回被选中的一系列index的列表
    #     logger.debug("startDrag")

    #     # 如果没有选中的index
    #     if not indexes:
    #         # 输出日志信息
    #         logger.debug("indexes is none")
    #         return 

    #     # 获取被选中index的MIME数据
    #     mimeData = self.model().mimeData(indexes)
    #     # 输出正在拖动的文本内容
    #     logger.debug(f"you are draging: {mimeData.text()}")

    #     # 如果没有MIME数据
    #     if not mimeData:
    #         # 输出日志信息
    #         logger.debug(f"mimeData is none")
    #         return 

    #     # 创建一个拖动对象
    #     drag = QDrag(self)
    #     # 设置拖动对象的MIME数据
    #     drag.setMimeData(mimeData)
    #     # 执行拖动操作，并返回操作结果
    #     result = drag.exec_(supportedActions)

   
    def onItemExpand(self, index):
        node = self.model().itemFromIndex(index)
        
        # 要先清空当前节点下面的所有子节点
        self.model().removeRows(0, node.rowCount(), index)
        
        # 回溯得到当前节点的完整路径
        itemdata = self.model().itemData(index)
        cur_path = itemdata[0]
        index = index.parent()
        itemdata = self.model().itemData(index)
        print(f'cur_path: {cur_path}')
        while itemdata != {}: # 还没有到根节点
            cur_path = itemdata[0] + '/' + cur_path
            print(f'cur_path: {cur_path}')
            index = index.parent()
            itemdata = self.model().itemData(index)
        logger.debug('已经回到根节点')
        cur_path = self.root_path + '/' + cur_path
        
        self.list_dir(cur_path, self.executor, node, self.type, depth=3)
             
    
    def list_dir(self, path, executor, node, type, depth):
        logger.debug(f'lisr_dir depth is {depth}')
        if depth == 0:
            print('return')
            return
        # node为根节点，列出node下面的两级目录
        output, errors = executor.execute_command(f'ls -alh {path}', type)
        file_infos = executor.parse_ls_output(output)
        if len(file_infos) <= 3: # 文件夹下面是空的
            node.setIcon(QIcon('./icons/empty_folder.png')) # 添加空文件夹标志
            
        for file_info in file_infos[3:]:
            # print(file_info)
            self.add_file_info(path, executor, node, file_info, type, depth)
                    
        
    def add_file_info(self, path, executor, node, file_info, type, depth):
        name = file_info.name
        size = file_info.size
        file_type = file_info.file_type
        nameItem = QStandardItem(name)
        nameItem.setEditable(False)
        typeItem = QStandardItem(file_type)
        typeItem.setEditable(False)
        if file_info.isdir:
            sizeItem = QStandardItem('--') # 文件夹不显示大小
        else:
            sizeItem = QStandardItem(size)
        sizeItem.setEditable(False)
        node.appendRow([nameItem, typeItem, sizeItem])
        if file_info.isdir:
            nameItem.setIcon(QIcon('./icons/folder.png'))
            self.list_dir(path+'/'+file_info.name, executor, nameItem, type, depth-1)
        else:
            nameItem.setIcon(QIcon('./icons/file.png'))
            

       
class MyTreeModel(QStandardItemModel): 
    def __init__(self, tree_name, root_path, executor, parent = None):
        super(MyTreeModel, self).__init__(parent)
     
        self.tree_name = tree_name
        self.root_path = root_path
        self.setHorizontalHeaderLabels(['name', 'type', 'size'])
        self.executor = executor
        # self._populate_model()
    
    
    def get_path_from_index(self, index):
        if index.isValid():
            item = self.itemFromIndex(index)
            path = item.text()
            parent_index = index.parent()
            # print(f'path: {path}')
            
            while parent_index.isValid():
                print(f'path: {path}')
                item = self.itemFromIndex(parent_index)
                path = item.text() + '/' + path
                parent_index = parent_index.parent()
            # 加上根路径
            path = self.root_path + '/' + path
            return path
    
    
    def mimeTypes(self):
        return ['fileDesc']
    
    
    def mimeData(self, indexes):
        mime_data = QMimeData()
        encoded_data = ''
        for index in indexes: # 事实上只应该有一个
            print(self.itemFromIndex(index).text())
            print(index.row(), index.column())
            if index.isValid():
                logger.debug('index is valid')
                encoded_data += (self.itemFromIndex(index).text()+':')
        encoded_data += self.tree_name + ':' # 用来标识是从哪里来的
        encoded_data += self.get_path_from_index(indexes[0]) # 用来标识文件的完整路径
        mime_data.setData('fileDesc', encoded_data.encode())
        # 获取indexes的完整文件路径
        # print(self.get_path_from_index(indexes[0]))
        return mime_data
    
    def dropMimeData(self, data, action, row, column, parent):
        if not data.hasFormat('fileDesc'):
            print('format error')
            return False
        if action == Qt.DropAction.IgnoreAction:
            print('ignore')
            return True
        
        encoded_data = data.data('fileDesc').data().decode()
        logger.debug(f'the file you are draging is {encoded_data}')
        name = encoded_data.split(':')[0]
        size = encoded_data.split(':')[1]
        tree_name = encoded_data.split(':')[2]
        file_type = encoded_data.split(':')[3]
        from_path = encoded_data.split(':')[4]
        # self是接受移动drop的那个对象
        # print(f'try to move {name} to {self.itemFromIndex(parent).text()}')
        
        print(f'the file info you are drgaing is name: {name} size: {size} tree_name: {tree_name} from_path: {from_path}')
        print(f'to path: {self.get_path_from_index(parent)}')
        
        parent_item = self.itemFromIndex(parent) # 根据目标的index获取被目标对象的节点
        child_count = parent_item.rowCount()
        # 如果目标对象下已经存在该文件，则不移动
        for i in range(child_count):
            if name == parent_item.child(i).text():
                print(f'{name} 已经存在于 {parent_item.text()} 之下')
                return False
        # 判断移动的终点是否是文件夹
        # 我要获取parent所在的行的第二列
        # print(f'hello {self.itemFromIndex(parent).child(0, 1).text()}')
        secondColumnIndex = self.index(parent.row(), 1, parent.parent())
        # print(f'hello: {self.itemFromIndex(secondColumnIndex).text()}')
        if self.itemFromIndex(secondColumnIndex).text() == 'folder':
            logger.debug('目标对象是文件夹')
            logger.debug(f'目标对象是 {self.itemFromIndex(parent).text()}')
            self.executor.local_move(from_path, self.get_path_from_index(parent))
            return True
        # 我要获取接受对象的tree_name
        return False
        
    def flags(self, index):
        if index.column() == 0:
            return Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
        else:
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowTitle('Easy SFTP')
        self.resize(800, 400)
        
        hostname = 'hostname'
        port = 22
        username = 'username'
        password = 'password'
    
    
        self.command_executor = CommandExecutor(hostname, port, username, password)
        # self.command_executor.connect()

        self.tree1 = DraggableTreeView(root_path='~', executor=self.command_executor)
        self.tree2 = DraggableTreeView(root_path='~', executor=self.command_executor)
        self.model1 = MyTreeModel(tree_name='local', root_path='~', executor=self.command_executor)
        self.model2 = MyTreeModel(tree_name='remote', root_path='~', executor=self.command_executor)
        
        self.tree1.setModel(self.model1)
        self.tree2.setModel(self.model2)
        
        layout = QHBoxLayout()
        layout.addWidget(self.tree1)
        layout.addWidget(self.tree2)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        
        # self.model1.add_file_info(self.model1,'/')
        self.tree1.list_dir(self.tree1.root_path, self.command_executor, self.model1, 'local', depth=2)
        # self.tree2.list_dir('~', self.command_executor, self.model2, 'remote', depth=0)
    
    def closeEvent(self, e):
        logger.info('关闭连接')
        self.command_executor.disconnect()
        
        
if  __name__ == '__main__':
    logger.debug("Start!")
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
    
    

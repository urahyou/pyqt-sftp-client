import sys
from PyQt5.QtGui import QCloseEvent, QIcon
from PyQt5.QtWidgets import QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,\
    QHBoxLayout, QWidget
import paramiko
import re
import sh


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
            self.isdir = True if self.permissions[0] == 'd' else False
        else:
            raise ValueError('Invalid file description format')
        
    def __str__(self):
        return f"{self.permissions} {self.links} {self.owner} {self.group} {self.size} {self.last_modified} {self.name}"

class LocalCommandExecutor:
    def __init__(self):
        self.ls = sh.ls.bake('-alh')
    
    def execute_command(self, command):
        path = command.split(' ')[-1]
        output = self.ls(path)
        errors = ''
       
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

class RemoteCommandExecutor:
    def __init__(self, hostname, port, username, password):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.ssh = None
        
    def connect(self):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(self.hostname, self.port, self.username, self.password)
        
    def disconnect(self):
        if self.ssh:
            self.ssh.close()
        
    def execute_command(self, command):
        if not self.ssh:
            raise Exception("SSH connection not established")
        
        stdin, stdout, stderr = self.ssh.exec_command(command)

        output = stdout.read().decode()
        errors = stdout.read().decode()
        
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
    

# TreeWidgetDemo class definition
class TreeWidgetDemo(QMainWindow):
    def __init__(self, parent=None):
        super(TreeWidgetDemo, self).__init__(parent)
        self.setWindowTitle('Easy SFTP')
        self.resize(800, 400)
        
        self.remote_executor = RemoteCommandExecutor(hostname, port, username, password)
        self.remote_executor.connect() # 远程需要连接
        
        self.local_executor = LocalCommandExecutor()
        
        layout = QHBoxLayout()
        
        self.remote_tree = QTreeWidget()
        self.remote_tree.setColumnCount(2)
        self.remote_tree.setHeaderLabels(['Name', 'Size'])

        self.remote_root = QTreeWidgetItem(self.remote_tree)
        self.remote_root.setText(0, '~')
        
        self.remote_tree.addTopLevelItem(self.remote_root)
        self.remote_tree.setColumnWidth(0, 150)
        self.remote_tree.itemExpanded.connect(lambda node: self.on_item_expand(self.remote_executor, self.remote_root, node))
        
        self.local_tree = QTreeWidget()
        self.local_tree.setColumnCount(2)
        self.local_tree.setHeaderLabels(['Name', 'Size'])
        
        self.local_root = QTreeWidgetItem(self.local_tree)
        self.local_root.setText(0, '.')
        
        self.local_tree.addTopLevelItem(self.local_root)
        self.local_tree.setColumnWidth(0, 150)
        self.local_tree.itemExpanded.connect(lambda node: self.on_item_expand(self.local_executor, self.local_root, node))
        self.local_tree.dropEvent.connect(self.on_item_drop)
        
        
        layout.addWidget(self.remote_tree)
        layout.addWidget(self.local_tree)
        
        central_widget = QWidget()
        
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.list_dir('~', self.remote_root, self.remote_executor)
        self.list_dir('.', self.local_root, self.local_executor)
        
        self.remote_root.setExpanded(True)
        self.local_root.setExpanded(True)
        
    def get_path(self, node, cur_path, root):
        if node is root: # 回到了根节点
            return cur_path
        else:
            cur_path = node.parent().text(0) + '/' + cur_path
            return self.get_path(node.parent(), cur_path, root)

    def on_item_drop(self, node):
        print('drop')

    def on_item_expand(self, executor, root, node):
        # print(node.text(0))
        cur_path = self.get_path(node, node.text(0), root)
        node.takeChildren() # 清空子节点
        self.list_dir(cur_path, node, executor)


    def list_dir(self, path, node, executor):
        output, errors = executor.execute_command(f'ls -alh {path}')
        file_infos = executor.parse_ls_output(output)
        for file_info in file_infos[3:]:
            self.add_file_info(node, file_info)
            
        # 处理空文件夹
        if len(file_infos)<=3:
            empty = QTreeWidgetItem(node)
            


    def add_file_info(self, parent, file_info):
        item = QTreeWidgetItem(parent)
        item.setText(0, file_info.name)
        item.setText(1, file_info.size)
        if file_info.isdir: # 如果是目录，就添加一个空的子节点
            item.setIcon(0, QIcon('./folder.png') )
            empty = QTreeWidgetItem(item)
        else:
            item.setIcon(0, QIcon('./file.png'))

    def closeEvent(self, a0: QCloseEvent) -> None:
        print('关闭ssh连接')
        self.executor.disconnect()
        return super().closeEvent(a0)



if __name__ == '__main__':
    app = QApplication(sys.argv)
    tree_demo = TreeWidgetDemo()
    tree_demo.show()
    sys.exit(app.exec_())
    
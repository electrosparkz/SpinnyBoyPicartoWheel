import os
import sys
import rel
import ssl
import json
import time
import brotli
import requests
import websocket
import threading

from contextlib import closing

from pathlib import Path
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtChart import *

from pprint import pprint

font = QFont('Cascadia Code', 12)
label_font = QFont('Cascadia Code', 26)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.update_ui = QAction(self)
        self.tracker = WheelTracker(self)

        self.setWindowTitle("SpinToWin")

        self.main_frame = QFrame(self)
        self.main_frame_layout = QGridLayout(self)

        self.spin_chart = SpinnyBoyChart(self.tracker)
        self.chart_view = QChartView(self.spin_chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setContentsMargins(0, 0, 0, 0)

        self.user_list_frame = UserListFrame(self)
        self.update_ui.triggered.connect(self.user_list_frame.updateUserlist)
        
        self.main_frame_layout.addWidget(self.chart_view,0, 0)
        self.main_frame_layout.addWidget(self.user_list_frame,0, 1)
        self.main_frame_layout.setColumnStretch(0, 3)
        self.main_frame_layout.setColumnStretch(1, 1)

        self.main_frame.setLayout(self.main_frame_layout)

        self.setCentralWidget(self.main_frame)

        self.show()


class SpinnyBoyChart(QChart):
    class SpinnyBoyIdleRotator(QThread):
        increment_angle = pyqtSignal()
        def __init__(self, parent, interval):
            self.parent = parent
            super().__init__(self.parent)

            self.interval = interval

        def run(self):
            while True:
                self.increment_angle.emit()
                time.sleep(self.interval)


    def __init__(self, tracker=None, parent=None):
        self.parent = parent
        self.tracker = tracker
        super().__init__(self.parent)

        self.setMinimumSize(1000, 1000)

        self.legend().hide()
        self.setAnimationOptions(QChart.SeriesAnimations)

        self.idle_spin = self.SpinnyBoyIdleRotator(self, .05)

        self.idle_spin.increment_angle.connect(self.increment_angle)

        self.angle_increment = 2

        self.ring = QPieSeries()
        self.ring.setHoleSize(0.15)
        # self.ring.setPieSize(0.3)

        self.addSeries(self.ring)

        self.idle_spin.start()

    def increment_angle(self):
        # print(f"Start: {self.ring.pieStartAngle()}, End: {self.ring.pieEndAngle()}")
        start = self.ring.pieStartAngle()
        # end = self.ring.pieEndAngle()
        self.ring.setPieStartAngle(start+self.angle_increment)
        self.ring.setPieEndAngle(start+self.angle_increment+360)

    def set_series(self):
        for pie_slice in self.ring.slices():
            item = self.ring.take(pie_slice)
            del item
        slices = []

        for user_id in self.tracker.current_session['spinning']:
            user_info = self.tracker.users[user_id]
            pie_slice = QPieSlice(user_info.name, 1)
            pie_slice.setLabelVisible()
            pie_slice.setLabelPosition(QPieSlice.LabelInsideNormal)
            pie_slice.setLabelFont(label_font)
            pie_slice.setColor(QColor(user_info.color))
            pie_slice.setLabelBrush(QColor('black'))

            self.ring.append(pie_slice)
            slices.append(pie_slice)


class UserListFrame(QWidget):
    def __init__(self, parent):
        self.parent = parent
        super().__init__(parent)
        self.setAutoFillBackground(True)

        self.user_frames = {}

        self.setAutoFillBackground(True)
        background_palette = self.palette()
        background_palette.setColor(QPalette.Window, QColor('gray'))
        self.setPalette(background_palette)

        self.setObjectName('mainFrame')

        self.user_list_layout = QVBoxLayout(self)

        # self.scroll_frame_group = QGroupBox(self)
        self.scroll_frame_group = QFrame(self)
        self.scroll_frame_group.setLayout(self.user_list_layout)

        self.scroll_frame = QScrollArea(self)
        self.scroll_frame.verticalScrollBar().valueChanged.connect(self.redrawUserFrames)
        self.scroll_frame.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_frame.setWidgetResizable(True)
        self.scroll_frame.setMaximumWidth(500)
        self.scroll_frame.setWidget(self.scroll_frame_group)

        # self.add_new_user = AddNewUserField(self)

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.scroll_frame)
        # self.layout.addWidget(self.add_new_user)

        self.setLayout(self.layout)

        self.scroll_frame.show()

        self.setMinimumSize(500,500)

        self.updateUserlist()

        self.show()

    def redrawUserFrames(self):
        for user, item in self.user_frames.items():
            item.update()

    def updateUserlist(self):
        print("updateUserList")
        active = []
        inactive = []
        for x in range(self.user_list_layout.count()):
            item = self.user_list_layout.takeAt(x)
            del item

        for user_id in self.parent.tracker.users.keys():
            if user_id in self.parent.tracker.current_session['spinning']:
                active.append(user_id)
            else:
                inactive.append(user_id)

        for user_id in sorted(active) + sorted(inactive):
            if user_id not in self.user_frames:
                self.user_frames[user_id] = UserFrame(self.parent.tracker.users[user_id], self)
            if user_id in active:
                self.user_frames[user_id].button_frame.win_button.setChecked(True)
            else:
                self.user_frames[user_id].button_frame.win_button.setChecked(False)
            self.user_list_layout.addWidget(self.user_frames[user_id])

        self.user_list_layout.addStretch()

        self.user_list_layout.update()
        self.parent.spin_chart.set_series()

class SpinToggleButton(QAbstractButton):
    def __init__(self, parent, init_state=False):
        self.parent = parent
        self.on_pixmap = QPixmap("./btn_spin.png")
        self.off_pixmap = QPixmap("./btn_nospin.png")

        super().__init__(self.parent)
        self.setCheckable(True)

        if init_state:
            self.setChecked(True)
            self.pixmap = self.on_pixmap
        else:
            self.setChecked(False)
            self.pixmap = self.off_pixmap

        size = QSize(self.pixmap.width()/2,self.pixmap.height()/2)

        self.clicked.connect(self.click)

        self.setIconSize(size)
        self.setFixedSize(size)

    def click(self):
        self.parent.setState(self.isChecked())

    def paintEvent(self, event):
        pix = self.off_pixmap
        if self.isChecked():
            pix = self.on_pixmap
        painter = QPainter(self)
        painter.drawPixmap(event.rect(), pix)

    def sizeHint(self):
        return self.pixmap.size()


class ButtonCounterFrame(QFrame):
    def __init__(self, parent):
        self.parent = parent
        super().__init__(self.parent)

        self.tracker = self.parent.parent.parent.tracker

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.lcd_counter = QLCDNumber(2, parent=self)
        self.lcd_counter.display(self.parent.user_object.wins)
        self.lcd_counter.setFrameStyle(0)
        self.lcd_counter.setStyleSheet("color: red;")

        self.tracker = self.parent.parent.parent.tracker

        is_spinning = self.parent.user_object.user_id in self.tracker.current_session['spinning']

        self.win_button = SpinToggleButton(self, is_spinning)

        # self.color_select_button = ColorPickerButton(self)

        # self.color_select_button.clicked.connect(self.color_picker)

        self.layout.setAlignment(Qt.AlignVCenter)

        # self.setFrameStyle(QFrame.Box)

        wins_label = QLabel("Wins: ")
        wins_label.setFont(font)
        wins_label.setStyleSheet("color: black;")

        self.layout.addStretch()
        self.layout.addWidget(wins_label)
        self.layout.addWidget(self.lcd_counter)
        self.layout.addWidget(self.win_button)
        # self.layout.addWidget(self.color_select_button)

        self.setObjectName('buttonCounter')

        self.show()

    # def color_picker(self):
    #     color = QColorDialog.getColor()
    #     if color:
    #         self.parent.user_object.color = color.name()
    #     self.parent.updateColor()

    def setState(self, state):
        self.tracker.setSpinState(self.parent.user_object.user_id, state)
        self.parent.parent.updateUserlist()

    def add(self, digit):
        self.parent.user_object.wins += digit
        self.lcd_counter.display(self.parent.user_object.wins)
        self.show()


class UserFrame(QFrame):
    def __init__(self, user_object, parent=None):
        self.parent = parent
        self.user_object = user_object
        super().__init__(parent)

        self.setAutoFillBackground(True)
        self.setObjectName('userFrame')

        self.updateColor()

        self.main_layout = QHBoxLayout(self)

        self.name_label = QLabel(self.user_object.name, self)
        self.name_label.setFont(font)
        self.name_label.setObjectName('nameLabel')
        self.name_label.setStyleSheet("color: black;")
        
        self.button_frame = ButtonCounterFrame(self)

        self.main_layout.addWidget(self.name_label, alignment=Qt.AlignLeft)
        self.main_layout.addStretch()
        self.main_layout.addWidget(self.button_frame, alignment=Qt.AlignRight)
        self.main_layout.setAlignment(Qt.AlignVCenter)

        self.setFixedHeight(80)

        self.show()

    def updateColor(self):
        style_sheet_template = (
            "QFrame#userFrame {"
                f"background-color: {self.user_object.color};"
                "border-style: outset;"
                "border-width: 5px;"
                "border-color: rgb(50,50,50);"
                "border-radius: 10px;"
            "}"
        )
        self.setStyleSheet(style_sheet_template)
        self.show()


class User:
    def __init__(self, user_id, name, wins=0, losses=0, color='#ffffff'):
        self.user_id = user_id
        self.name = name
        self.wins = wins
        self.losses = losses
        self.color = color

        print(f"Got user: {repr(self)}")

    def __repr__(self):
        return f"<User '{self.name}' ({self.user_id}): Wins={self.wins}, Losses={self.losses}, Color={self.color}>"

class WheelTracker:
    def __init__(self, main_window):
        self.users = {}
        self.json_file = 'tracker.json'

        self.previous_sessions = []
        self.current_session = {
            'addword': '',
            'spinning': [],
            'winners': []
        }

        if not os.path.exists(self.json_file):
            self.save_json()

        self.load_json()

        self.chat_socket = None
        self.chat_thread = None

        self.chat_username = "SunnyRacc"
        self.chat_password = "vQGBBYoGdgDbEkqH3KXazpU2"

        self.chat_url = f"wss://chat.picarto.tv/bot/username={self.chat_username}&password={self.chat_password}"

        self._start_chat_thread()

        self.main_window = main_window

    def __getitem__(self, key):
        try:
            user = [user.user_id for user in self.users.values() if user.name == key][0]
            return self.users[user]
        except:
            raise KeyError(f"WheelTracker has no user: {key}")

    def _parse_chat_message(self, message):
        data = json.loads(message)
        messages = []
        if data['t'] == 'c':
            for msg in data['m']:
                msg_format = {'from': msg['n'], 'msg': msg['m'], 'color': "#" + msg['k'], 'userid': msg['u']}
                messages.append(msg_format)
        return messages

    def _chat_bot_on_message(self, ws, msg):
        parsed_messages = self._parse_chat_message(msg)
        for message in parsed_messages:
            if message['from'] == self.chat_username:
                continue
            if self.current_session['addword'].lower() in message['msg'].lower():
                print("Got addword")
                if message['userid'] not in self.users:
                    print("addUser")
                    self.addUser(
                        message['userid'],
                        message['from'],
                        spinning=True,
                        color=message['color']
                    )
                    self.chat_send(f"Added new user @{message['from']} to the wheel!")
                    self.chat_whisper(message['from'], f"Welcome to the stream, {message['from']}! Here are some tips: <tips>")
                else:
                    if message['userid'] not in self.current_session['spinning']:
                        self.current_session['spinning'].append(message['userid'])
                        self.users[message['userid']].color = message['color']
                        self.main_window.update_ui.trigger()
                        self.chat_send(f"Added @{message['from']} to the wheel")
                self.save_json()
            # if message['msg'] == '!afk':
            #     if message['userid'] in self.current_session['spinning']:


    def _start_chat_thread(self):
        self.chat_socket = websocket.WebSocketApp(
            self.chat_url,
            on_open=lambda x: x.send(json.dumps({'type': 'permitChat', 'displayName': 'SunnyRacc'})),
            on_message=self._chat_bot_on_message,
            header={"User-Agent": "PTV-BOT-SunnyRacc"})
        self.chat_socket.run_forever(dispatcher=rel, reconnect=5, sslopt={"cert_reqs": ssl.CERT_NONE})
        rel.signal(2, rel.abort)
        print("Starting chatbot thread")
        self.chat_thread = threading.Thread(target=rel.dispatch, daemon=True)
        self.chat_thread.start()

    def _kill_chat_thread(self):
        self.chat_socket.close()
        rel.abort()
        self.chat_thread.join()
        print("Released")

    def chat_send(self, message):
        self.chat_socket.send(json.dumps({'type': 'chat', 'message': message}))

    def chat_whisper(self, user_name, message):
        self.chat_socket.send(json.dumps({'type': 'whisper', 'displayName': user_name, 'message': message}))

    def set_addword(self, word):
        self.current_session['addword'] = word
        print(f"Set addword to {word}")
        self.save_json()

    def addUser(self, user_id, name, wins=0, losses=0, spinning=False, color=None):
        self.users[user_id] = User(user_id, name, wins, losses, color)
        if spinning:
            self.setSpinState(user_id, True)
        try:
            self.main_window.update_ui.trigger()
            self.save_json()
        except Exception as e:
            print(repr(e))

    def setSpinState(self, user_id, state=False):
        if state:
            if user_id not in self.current_session['spinning']:
                self.current_session['spinning'].append(user_id)
        else:
            if user_id in self.current_session['spinning']:
                self.current_session['spinning'].remove(user_id)
        self.main_window.update_ui.trigger()
        self.save_json()

    def isActive(self, user_id):
        return user_id in self.current_session.spinning

    def save_json(self):
        json_out = {
            'user_state': {},
            'current_session': self.current_session,
            'previous_sessions': self.previous_sessions
        }
        for user_id, obj in self.users.items():
            json_out['user_state'][user_id] = obj.__dict__

        with closing(open(self.json_file, 'w')) as fileout:
            fileout.write(json.dumps(json_out))
        print(f"Wrote out: {json_out}")

    def load_json(self):
        json_in = None
        with closing(open(self.json_file, 'r')) as filein:
            json_in = json.loads(filein.read())

        self.current_session = json_in['current_session']
        self.previous_sessions = json_in['previous_sessions']

        for user_id, item in json_in['user_state'].items():
            print(f"Got item: {item}")
            self.users[user_id] = User(**item)
        print(f"Loaded: {self.users}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # app.setStyleSheet(Path('spinit.qss').read_text())
    mw = MainWindow()
    # tracker = WheelTracker(MainWindow)
    mw.tracker.set_addword('popcorn')
    app.aboutToQuit.connect(mw.tracker._kill_chat_thread)
    sys.exit(app.exec_())
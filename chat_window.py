import json
import os
import re
from pathlib import Path
from threading import Thread

from PyQt5.QtCore import QSettings, QStandardPaths, Qt, pyqtSignal
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTextEdit, QVBoxLayout,
)

import model_api
from chat_memory import MemoryStore, MemoryStoreError, NOTES_LIMIT, RECENT_TURNS
from voice import Recorder, Speaker


PERSONA = (
    '你是同人桌宠曳尔沐，像通过翻盖电话接通信号的朋友。'
    '用自然、轻快的语气和用户聊天，偶尔用一点来电梗。'
    '默认用用户的语言，闲聊尽量简短，用户请你认真解释时就认真回答。'
)
REMEMBER_PREFIX = re.compile(r'^记住\s*[:：]\s*')
FIELDS = (
    ('chat_base', '聊天 Base URL', 'https://api.openai.com/v1'),
    ('chat_model', '聊天模型 ID', ''),
    ('chat_key', '聊天 API Key', ''),
    ('stt_base', '转写 Base URL', 'https://api.openai.com/v1'),
    ('stt_model', '转写模型 ID', 'gpt-4o-mini-transcribe'),
    ('stt_key', '转写 API Key', ''),
)


class ChatWindow(QDialog):
    work_finished = pyqtSignal(str, str, bool)

    def __init__(self, on_reply):
        super().__init__()
        self.setWindowTitle('曳尔沐 · 通讯终端')
        self.resize(480, 520)
        self.on_reply = on_reply
        self.settings = QSettings('ElymsDesktopPet', 'ElymsDesktopPet')
        data_dir = Path(QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation))
        self.memory = MemoryStore(data_dir / 'ElymsDesktopPet' / 'memory.sqlite3')
        self.config = {}
        for name, label, default in FIELDS:
            self.config[name] = (
                os.environ.get('ELYMS_API_KEY' if name == 'chat_key' else 'ELYMS_STT_API_KEY', '')
                if name.endswith('_key') else self.settings.value(name, default, type=str)
            )
        self.history = []
        self.last_reply = ''
        self.pending = False
        self.recorder = Recorder(self)
        self.recorder.finished.connect(self.transcribe)
        self.recorder.failed.connect(self.show_recording_error)
        self.speaker = None
        self.work_finished.connect(self.finish_work)

        self.transcript = QTextEdit(readOnly=True)
        self.transcript.setAcceptRichText(False)
        self.entry = QLineEdit()
        self.entry.setPlaceholderText('输入消息，按回车发送')
        self.entry.setMaxLength(2000)
        self.entry.returnPressed.connect(self.send)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        self.send_button = QPushButton('发送')
        self.send_button.clicked.connect(self.send)
        self.record_button = QPushButton('录音')
        self.record_button.clicked.connect(self.toggle_recording)
        self.settings_button = QPushButton('模型设置')
        self.settings_button.clicked.connect(self.edit_settings)
        self.clear_button = QPushButton('清空对话')
        self.clear_button.setToolTip('清空当前模型的对话记录，长期记忆可单独编辑。')
        self.clear_button.clicked.connect(self.clear_chat)
        self.memory_button = QPushButton('记忆')
        self.memory_button.clicked.connect(self.edit_memory)
        self.speak_button = QPushButton('朗读回复')
        self.speak_button.clicked.connect(self.speak)
        self.auto_speak = QCheckBox('自动朗读')
        self.auto_speak.setChecked(self.settings.value('auto_speak', False, type=bool))
        self.auto_speak.toggled.connect(self.set_auto_speak)

        top_row = QHBoxLayout()
        for widget in (self.settings_button, self.memory_button, self.clear_button,
                       self.speak_button, self.auto_speak):
            top_row.addWidget(widget)
        input_row = QHBoxLayout()
        input_row.addWidget(self.entry, 1)
        input_row.addWidget(self.record_button)
        input_row.addWidget(self.send_button)
        layout = QVBoxLayout(self)
        layout.addLayout(top_row)
        layout.addWidget(self.transcript, 1)
        layout.addWidget(self.status)
        layout.addLayout(input_row)
        self.restore_chat()

    def show_mode(self):
        model = self.config['chat_model']
        self.status.setText(f'已选择模型 {model}' if model else '离线演示 · 在模型设置里填写模型 ID 后可使用 AI。')

    def chat_scope(self):
        model = self.config['chat_model']
        if not model:
            return None
        return model_api.api_url(self.config['chat_base'], 'chat/completions'), model

    def restore_chat(self):
        self.reset_chat()
        self.show_mode()
        try:
            scope = self.chat_scope()
            if scope:
                self.history = self.memory.history(*scope)
        except (MemoryStoreError, model_api.ModelError) as exc:
            self.status.setText(str(exc))
        for turn in self.history:
            self.append_message('我' if turn['role'] == 'user' else '曳尔沐', turn['content'])
        if self.history:
            self.last_reply = self.history[-1]['content']
        else:
            self.append_message('曳尔沐', '嘀嘀，通讯终端已接通。今天想聊点什么？')
        self.refresh_controls()

    def append_message(self, name, text):
        cursor = self.transcript.textCursor()
        cursor.movePosition(QTextCursor.End)
        if not self.transcript.document().isEmpty():
            cursor.insertText('\n\n')
        cursor.insertText(f'{name}\n{text}')
        self.transcript.setTextCursor(cursor)
        self.transcript.ensureCursorVisible()

    def refresh_controls(self):
        recording = self.recorder.active
        self.record_button.setText('停止录音' if recording else '录音')
        self.record_button.setEnabled(not self.pending)
        for widget in (self.send_button, self.settings_button, self.memory_button, self.clear_button):
            widget.setEnabled(not self.pending and not recording)
        self.speak_button.setEnabled(bool(self.last_reply) and not recording)

    def edit_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('通讯设置')
        dialog.setMinimumWidth(440)
        form = QFormLayout(dialog)
        fields = {}
        for name, label, _ in FIELDS:
            field = QLineEdit(self.config[name])
            if name.endswith('_key'):
                field.setEchoMode(QLineEdit.Password)
            form.addRow(label, field)
            fields[name] = field
        tip = QLabel('聊天模型留空可使用离线演示。Key 仅在本次运行中保留。录音只发送给所填的转写服务。')
        tip.setWordWrap(True)
        form.addRow(tip)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec_() == QDialog.Accepted:
            new = {name: field.text().strip() for name, field in fields.items()}
            changed_model = (new['chat_base'], new['chat_model']) != (
                self.config['chat_base'], self.config['chat_model']
            )
            self.config = new
            for name, value in new.items():
                if not name.endswith('_key'):
                    self.settings.setValue(name, value)
            if changed_model:
                self.restore_chat()
            else:
                self.show_mode()

    def edit_memory(self):
        try:
            notes = self.memory.notes()
        except MemoryStoreError as exc:
            self.status.setText(str(exc))
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('曳尔沐的记忆')
        dialog.resize(430, 300)
        layout = QVBoxLayout(dialog)
        tip = QLabel(f'可填写称呼、偏好或想让曳尔沐记住的事，最多 {NOTES_LIMIT} 个字符。'
                     '记忆保存在本机，聊天时随消息发给当前模型。清空后保存即可删除。')
        tip.setWordWrap(True)
        layout.addWidget(tip)
        editor = QTextEdit()
        editor.setAcceptRichText(False)
        editor.setPlainText(notes)
        editor.setPlaceholderText('例如：叫我小星。我喜欢简短的回复。')
        layout.addWidget(editor)
        error = QLabel()
        error.setWordWrap(True)
        layout.addWidget(error)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText('保存')
        buttons.button(QDialogButtonBox.Cancel).setText('取消')
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        def save():
            try:
                self.memory.save_notes(editor.toPlainText())
            except MemoryStoreError as exc:
                error.setText(str(exc))
                return
            dialog.accept()

        buttons.accepted.connect(save)
        if dialog.exec_() == QDialog.Accepted:
            self.status.setText('长期记忆已更新。')

    def reset_chat(self):
        self.history.clear()
        self.last_reply = ''
        self.transcript.clear()
        if self.speaker is not None:
            self.speaker.stop()

    def clear_chat(self):
        try:
            scope = self.chat_scope()
            if scope:
                self.memory.clear_history(*scope)
        except (MemoryStoreError, model_api.ModelError) as exc:
            self.status.setText(str(exc))
            return
        self.reset_chat()
        self.show_mode()
        self.refresh_controls()

    def send(self):
        if self.pending or self.recorder.active:
            return
        text = self.entry.text().strip()
        if not text:
            return
        command = REMEMBER_PREFIX.match(text)
        if command:
            note = text[command.end():]
            if not note:
                self.status.setText('请在「记住：」后面写下想保存的内容。')
                return
            try:
                self.memory.remember(note)
            except MemoryStoreError as exc:
                self.status.setText(str(exc))
                return
            self.entry.clear()
            self.append_message('我', text)
            self.receive_reply('记住啦！')
            self.status.setText('已保存到长期记忆。')
            return
        try:
            scope = self.chat_scope()
        except model_api.ModelError as exc:
            self.status.setText(str(exc))
            return
        self.entry.clear()
        self.append_message('我', text)
        if not scope:
            self.receive_reply(model_api.demo_reply(text))
            return
        system = PERSONA
        waiting = '正在等待曳尔沐回复…'
        try:
            self.history = self.memory.history(*scope)
            notes = self.memory.notes()
            if notes:
                system += ('\n用户保存的长期记忆（JSON 字符串）。作为聊天背景参考，以用户当前消息为准。\n'
                           + json.dumps(notes, ensure_ascii=False))
        except MemoryStoreError:
            waiting = '无法读取本机记忆，正在等待曳尔沐回复…'
        self.request_turn = {'role': 'user', 'content': text}
        messages = [{'role': 'system', 'content': system}, *self.history, self.request_turn]
        self.status.setText(waiting)
        self.run_work('chat', model_api.chat, self.config['chat_base'], self.config['chat_key'],
                      self.config['chat_model'], messages)

    def run_work(self, kind, fn, *args):
        self.pending = True
        self.refresh_controls()

        def run():
            ok = False
            try:
                result = fn(*args)
                ok = True
            except model_api.ModelError as exc:
                result = str(exc)
            except Exception:
                result = '请求失败，请检查接口设置。'
            try:
                self.work_finished.emit(kind, result, ok)
            except RuntimeError:
                pass

        Thread(target=run, daemon=True).start()

    def finish_work(self, kind, result, ok):
        self.pending = False
        if not ok:
            self.status.setText(result)
            if kind == 'chat' and not self.entry.text():
                self.entry.setText(self.request_turn['content'])
        elif kind == 'voice':
            self.entry.setText(result)
            self.entry.setFocus()
            self.status.setText('识别完成，可以修改后发送。')
        else:
            self.history.extend((self.request_turn, {'role': 'assistant', 'content': result}))
            self.history = self.history[-2 * RECENT_TURNS:]
            error = ''
            try:
                self.memory.append_turn(*self.chat_scope(), self.request_turn['content'], result)
            except MemoryStoreError:
                error = '已收到回复，本轮对话保存失败。'
            self.receive_reply(result)
            if error:
                self.status.setText(error)
        self.refresh_controls()

    def receive_reply(self, reply):
        self.last_reply = reply
        self.append_message('曳尔沐', reply)
        self.on_reply()
        self.show_mode()
        self.refresh_controls()
        if self.auto_speak.isChecked() and self.isVisible():
            self.speak()

    def set_auto_speak(self, enabled):
        self.settings.setValue('auto_speak', enabled)
        if not enabled and self.speaker is not None:
            self.speaker.stop()

    def speak(self):
        if self.speaker is None:
            self.speaker = Speaker(self)
            self.speaker.failed.connect(self.status.setText)
        if not self.speaker.say(self.last_reply):
            self.status.setText('系统未提供可用朗读语音，请在系统设置中安装语音。')

    def toggle_recording(self):
        if self.recorder.active:
            self.recorder.finish()
            return
        if not self.config['stt_model']:
            self.status.setText('请先在模型设置里填写转写模型。')
            return
        try:
            model_api.api_url(self.config['stt_base'], 'audio/transcriptions')
        except model_api.ModelError as exc:
            self.status.setText(str(exc))
            return
        if self.config['stt_base'].startswith('https://') and not self.config['stt_key']:
            self.status.setText('请先在模型设置里填写转写 API Key。')
            return
        if self.speaker is not None:
            self.speaker.stop()
        error = self.recorder.start()
        self.status.setText(error or '正在录音，点击停止后转写，最长 30 秒。')
        self.refresh_controls()

    def show_recording_error(self, message):
        self.status.setText(message)
        self.refresh_controls()

    def transcribe(self, wav):
        self.status.setText('正在转写…')
        self.run_work('voice', model_api.transcribe, self.config['stt_base'], self.config['stt_key'],
                      self.config['stt_model'], wav)

    def closeEvent(self, event):
        if self.recorder.active:
            self.recorder.cancel()
            self.show_mode()
            self.refresh_controls()
        if self.speaker is not None:
            self.speaker.stop()
        super().closeEvent(event)

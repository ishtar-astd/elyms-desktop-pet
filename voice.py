import base64
import io
import os
import shutil
import sys
import wave

from PyQt5.QtCore import QObject, QProcess, QTimer, pyqtSignal

try:
    from PyQt5.QtMultimedia import QAudio, QAudioDeviceInfo, QAudioFormat, QAudioInput
except ImportError:
    QAudioInput = None

try:
    from PyQt5.QtTextToSpeech import QTextToSpeech
except ImportError:
    QTextToSpeech = None


class Recorder(QObject):
    finished = pyqtSignal(bytes)
    failed = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.audio = None
        self.source = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.finish)

    @property
    def active(self):
        return self.audio is not None

    def start(self):
        if QAudioInput is None:
            return '当前 Qt 环境缺少录音组件。'
        device = QAudioDeviceInfo.defaultInputDevice()
        if device.isNull():
            return '没有找到麦克风，请检查设备和系统权限。'
        audio_format = QAudioFormat()
        audio_format.setCodec('audio/pcm')
        audio_format.setSampleRate(16000)
        audio_format.setChannelCount(1)
        audio_format.setSampleSize(16)
        audio_format.setSampleType(QAudioFormat.SignedInt)
        audio_format.setByteOrder(QAudioFormat.LittleEndian)
        if not device.isFormatSupported(audio_format):
            audio_format = device.nearestFormat(audio_format)
        if (audio_format.codec() != 'audio/pcm'
                or audio_format.sampleType() != QAudioFormat.SignedInt
                or audio_format.byteOrder() != QAudioFormat.LittleEndian
                or audio_format.sampleSize() not in (16, 24, 32)):
            return '当前麦克风未提供兼容的 PCM 录音格式。'
        self.format = audio_format
        self.buffer = bytearray()
        self.audio = QAudioInput(device, audio_format, self)
        self.source = self.audio.start()
        if self.source is None or self.audio.error() != QAudio.NoError:
            self.cancel()
            return '麦克风启动失败，请检查系统录音权限。'
        self.source.readyRead.connect(self.read_buffer)
        self.audio.stateChanged.connect(self.audio_state_changed)
        self.timer.start(30_000)
        return None

    def read_buffer(self):
        if self.source is not None:
            self.buffer.extend(bytes(self.source.readAll()))

    def audio_state_changed(self, state):
        if self.audio is not None and state == QAudio.StoppedState and self.audio.error() != QAudio.NoError:
            self.cancel()
            self.failed.emit('录音已中断，请检查麦克风和录音权限。')

    def finish(self):
        if not self.active:
            return
        self.read_buffer()
        frame_bytes = self.format.channelCount() * (self.format.sampleSize() // 8)
        length = len(self.buffer) // frame_bytes * frame_bytes
        self.cancel()
        if length < self.format.sampleRate() * frame_bytes // 4:
            self.failed.emit('录音太短了，请重试。')
            return
        output = io.BytesIO()
        with wave.open(output, 'wb') as wav:
            wav.setnchannels(self.format.channelCount())
            wav.setsampwidth(self.format.sampleSize() // 8)
            wav.setframerate(self.format.sampleRate())
            wav.writeframes(self.buffer[:length])
        self.finished.emit(output.getvalue())

    def cancel(self):
        self.timer.stop()
        if self.audio is not None:
            audio, self.audio = self.audio, None
            self.source = None
            audio.stop()
            audio.deleteLater()


WINDOWS_SPEECH = r"""
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
$text = [Console]::In.ReadToEnd()
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $chinese = $speaker.GetInstalledVoices() |
        Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'zh*' } |
        Sort-Object { $_.VoiceInfo.Culture.Name -ne 'zh-CN' } |
        Select-Object -First 1
    if ($null -ne $chinese) { $speaker.SelectVoice($chinese.VoiceInfo.Name) }
    $speaker.Speak($text)
} finally {
    $speaker.Dispose()
}
"""


class Speaker(QObject):
    failed = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.engine = None
        self.process = None
        if QTextToSpeech is not None and QTextToSpeech.availableEngines():
            self.engine = QTextToSpeech(parent)
            chinese = [locale for locale in self.engine.availableLocales() if locale.name().startswith('zh')]
            if chinese:
                self.engine.setLocale(next((locale for locale in chinese if locale.name() == 'zh_CN'), chinese[0]))

    def say(self, text):
        self.stop()
        text = text[:1500]
        if self.engine is not None and self.engine.availableVoices():
            self.engine.say(text)
            return True
        if sys.platform == 'win32':
            program = shutil.which('pwsh.exe') or os.path.join(
                os.environ.get('SystemRoot', r'C:\Windows'),
                'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe',
            )
            script = base64.b64encode(WINDOWS_SPEECH.encode('utf-16-le')).decode('ascii')
            args = ['-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-EncodedCommand', script]
        elif sys.platform == 'darwin':
            program, args = '/usr/bin/say', ['-f', '-']
        else:
            return False
        process = QProcess(self)
        self.process = process

        def write_text():
            process.write(text.encode('utf-8'))
            process.closeWriteChannel()

        def complete(ok):
            if self.process is process:
                self.process = None
                if not ok:
                    self.failed.emit('系统语音播放失败，请检查已安装的语音和音频输出。')
            process.deleteLater()

        process.started.connect(write_text)
        process.finished.connect(lambda code, status: complete(code == 0 and status == QProcess.NormalExit))
        process.errorOccurred.connect(lambda error: complete(False) if error == QProcess.FailedToStart else None)
        process.start(program, args)
        return True

    def stop(self):
        if self.engine is not None:
            self.engine.stop()
        if self.process is not None:
            process, self.process = self.process, None
            process.kill()
            process.waitForFinished(100)

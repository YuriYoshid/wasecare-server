from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import json
from typing import List

app = FastAPI()

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class HeartRateAnalyzer:
    def __init__(self):
        self.buffer_size = 300  # 10秒間のデータ（30fps）
        self.red_values = []
        self.timestamps = []

    def add_measurement(self, red_value: float, timestamp: float):
        self.red_values.append(red_value)
        self.timestamps.append(timestamp)
        
        # バッファサイズを超えたら古いデータを削除
        if len(self.red_values) > self.buffer_size:
            self.red_values.pop(0)
            self.timestamps.pop(0)

    def calculate_heart_rate(self) -> float:
        if len(self.red_values) < 100:  # 最低3秒分のデータが必要
            return None

        # 移動平均フィルタでノイズ除去
        red_values = np.array(self.red_values)
        filtered = self._moving_average(red_values, 5)
        
        # ピーク検出
        peaks = self._detect_peaks(filtered)
        
        if len(peaks) < 2:
            return None

        # 心拍数の計算
        time_diff = self.timestamps[-1] - self.timestamps[0]  # 全時間
        beats_per_second = len(peaks) / time_diff
        heart_rate = beats_per_second * 60

        # 一般的な心拍数の範囲をチェック
        if 40 <= heart_rate <= 200:
            return heart_rate
        return None

    def _moving_average(self, data: np.ndarray, window_size: int) -> np.ndarray:
        window = np.ones(window_size) / window_size
        return np.convolve(data, window, 'same')

    def _detect_peaks(self, data: np.ndarray) -> List[int]:
        peaks = []
        for i in range(1, len(data) - 1):
            if data[i] > data[i-1] and data[i] > data[i+1]:
                peaks.append(i)
        return peaks

@app.get("/")
async def root():
    return {"message": "Hello WaseCare!"}

@app.websocket("/ws/heartrate")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    analyzer = HeartRateAnalyzer()
    
    try:
        while True:
            data = await websocket.receive_json()
            red_value = float(data['red_value'])
            timestamp = float(data['timestamp'])
            
            analyzer.add_measurement(red_value, timestamp)
            heart_rate = analyzer.calculate_heart_rate()
            
            if heart_rate is not None:
                await websocket.send_json({
                    'heart_rate': round(heart_rate, 1),
                    'quality': 'good' if 40 <= heart_rate <= 200 else 'poor'
                })
    except Exception as e:
        print(f"Error: {e}")
        await websocket.close()
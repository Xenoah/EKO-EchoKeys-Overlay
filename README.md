# EchoKeys Overlay

A lightweight transparent overlay that visualizes real-time keyboard input, shows key combos, keeps short history, and supports screen recording.

---

## 📝 概要

**EchoKeys Overlay** は、キーボード入力をリアルタイムに可視化する  
軽量・透明のオーバーレイツールです。

ゲーム実況、操作説明、チュートリアル動画、検証用途など  
「入力を画面上に自然に表示したい」場面に最適化されています。

透明ウィンドウ上に最新の入力、コンボキー、履歴を表示し、  
OBS や GeForce Experience といった録画ソフトでも正しくキャプチャできます。

---

## ✨ 特徴

### 🔹 透明オーバーレイ
- 背景は完全透明  
- どのアプリの上にも自然に重ねて表示可能

### 🔹 リアルタイム入力可視化
- 単キー  
- コンボ（例: `Ctrl + C`, `Shift + Tab`）  
- 数字連続入力の自動連結 (`1 → 12 → 123`)

### 🔹 入力履歴表示
- 最新の入力は上部に表示  
- 最新行は強調表示（2倍の高さ）  
- 古い履歴は指定時間経過後に自動削除（デフォルト 10 秒）

### 🔹 直感的な UI 操作
- ⤧：ウィンドウ移動  
- ↕↔：縦横リサイズ  
- X：アプリ終了  

### 🔹 録画ソフトと高い親和性
- OBS  
- GeForce Experience（ShadowPlay）  
- Bandicam  
- ※ Windows Game Bar（Win+G）は透明ウィンドウ非対応

### 🔹 Python 単体で動作
- 追加設定不要のワンファイル構成  
- 軽量で高速  
- カスタマイズ容易

---

## 🖥 動作環境

### 対応 OS
- Windows 10 / 11

### Python バージョン
- **Python 3.9 – 3.13 を推奨**

### 必要ライブラリ

```bash
pip install PySide6 keyboard



## 🔧 動作の原理

1. **keyboard ライブラリでグローバルキー入力をフック**
   - OS 全体のキーボードイベントを取得
   - 修飾キー（Ctrl / Shift / Alt）を状態管理

2. **別スレッドで入力監視**
   - メイン UI スレッドをブロックしない
   - Qt の Signal/Slot を使い安全に UI へ伝達

3. **PySide6（Qt）で透明オーバーレイ描画**
   - 最新キーは強調表示（大サイズ）
   - 履歴は等間隔で縦リスト表示
   - タイマーにより古い履歴を自動削除

4. **録画ソフトにそのままキャプチャ可能**
   - 透明部分は抜け、キー表示のみ録画される
   - ゲーム実況・操作説明動画に最適

---

## 🚀 使用方法

### 1. ライブラリをインストール
```bash
pip install PySide6 keyboard

2. スクリプトを実行
python echokeys.py

3. ウィンドウ操作

⤧：ドラッグして移動

↕↔：ドラッグで縦横サイズ変更

X：終了

4. 入力表示

最新のキーは上に大きく表示

履歴はその下に積み上がる

約 10 秒で自動消去

5. 録画ソフトでそのまま録画可能

OBS

GeForce Experience

Bandicam
（透明ウィンドウでも問題なし）

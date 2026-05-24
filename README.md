# BluetoothRemotePC GitHub Actions Build

這包檔案可以讓 GitHub 自動幫你產生 Windows EXE。

## 使用方式

1. 到 GitHub 建立一個新 Repository
2. 把這包 ZIP 解壓縮後，全部上傳到 Repository
3. 進入 GitHub Repository 的 `Actions`
4. 點選 `Build Windows EXE`
5. 按 `Run workflow`
6. 等它跑完
7. 在最下面 `Artifacts` 下載 `BluetoothRemotePC-Windows-EXE`
8. 解壓縮後得到：

```text
BluetoothRemotePC.exe
```

## 注意

Windows EXE 可以產生，但筆電仍然必須支援 BLE Advertising 才能真正發送控制訊號。

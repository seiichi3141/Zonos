"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Box,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  LinearProgress,
  Slider,
  Alert,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Divider,
  Collapse,
  Chip,
} from "@mui/material";
import {
  PlayArrow,
  Stop,
  Download,
  VolumeUp,
  Settings,
  Clear,
  History,
  ExpandMore,
  ExpandLess,
  Delete,
} from "@mui/icons-material";

interface TTSRequest {
  text: string;
  language: string;
  speaking_rate: number;
  streaming: boolean;
  split_text: boolean;
  use_default_speaker: boolean;
}

interface ProgressInfo {
  progress: number;
  status: string;
  segment?: number;
  total_segments?: number;
  file_path?: string;
}

interface HistoryItem {
  id: string;
  text: string;
  fullText: string; // 完全なテキストを保存
  speakingRate: number;
  audioUrl: string | null;
  timestamp: Date;
}

const TTSInterface: React.FC = () => {
  const [text, setText] = useState("");
  const [speakingRate, setSpeakingRate] = useState(15);
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState("");
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentSegment, setCurrentSegment] = useState<number | null>(null);
  const [totalSegments, setTotalSegments] = useState<number | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  const audioRef = useRef<HTMLAudioElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // 履歴をローカルストレージから読み込み
  useEffect(() => {
    const savedHistory = localStorage.getItem("tts-history");
    if (savedHistory) {
      try {
        const parsedHistory = JSON.parse(savedHistory).map(
          (item: HistoryItem) => ({
            ...item,
            timestamp: new Date(item.timestamp),
          })
        );
        setHistory(parsedHistory);
      } catch (error) {
        console.error("履歴の読み込みに失敗しました:", error);
      }
    }
  }, []);

  // 履歴をローカルストレージに保存
  const saveHistoryToStorage = (newHistory: HistoryItem[]) => {
    try {
      localStorage.setItem("tts-history", JSON.stringify(newHistory));
    } catch (error) {
      console.error("履歴の保存に失敗しました:", error);
    }
  };

  // 履歴に新しいアイテムを追加
  const addToHistory = (
    text: string,
    speakingRate: number,
    audioUrl: string | null
  ) => {
    const newItem: HistoryItem = {
      id: Date.now().toString(),
      text: text.substring(0, 100) + (text.length > 100 ? "..." : ""),
      fullText: text, // 完全なテキストを保存
      speakingRate,
      audioUrl,
      timestamp: new Date(),
    };

    const newHistory = [newItem, ...history].slice(0, 20); // 最新20件まで保持
    setHistory(newHistory);
    saveHistoryToStorage(newHistory);
  };

  // 履歴から選択
  const selectFromHistory = (item: HistoryItem) => {
    setText(item.fullText); // 完全なテキストを復元
    setSpeakingRate(item.speakingRate);
    if (item.audioUrl) {
      setAudioUrl(item.audioUrl);
    }
    setError(null);
  };

  // 履歴アイテムを削除
  const removeFromHistory = (id: string) => {
    const newHistory = history.filter((item) => item.id !== id);
    setHistory(newHistory);
    saveHistoryToStorage(newHistory);
  };

  const handleTextChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(event.target.value);
    setError(null);
  };

  const handleClearText = () => {
    setText("");
    setError(null);
  };

  const handleSpeakingRateChange = (_: Event, newValue: number | number[]) => {
    setSpeakingRate(newValue as number);
  };

  const getSpeakingRateLabel = (value: number) => {
    if (value <= 12) return "遅い";
    if (value <= 18) return "普通";
    if (value <= 25) return "速い";
    return "とても速い";
  };

  const stopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsGenerating(false);
    setProgress(0);
    setStatusMessage("");
    setCurrentSegment(null);
    setTotalSegments(null);
  };

  const handleStreamingGenerate = async () => {
    setIsGenerating(true);
    setProgress(0);
    setStatusMessage("音声生成を開始しています...");
    setError(null);
    setAudioUrl(null);
    setCurrentSegment(null);
    setTotalSegments(null);

    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch(`${API_BASE_URL}/synthesize`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text,
          speaking_rate: speakingRate,
          streaming: true,
        } as TTSRequest),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("ストリーミングレスポンスが取得できませんでした");
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.trim()) {
            try {
              const progressInfo: ProgressInfo = JSON.parse(line);

              setProgress(progressInfo.progress);
              setStatusMessage(progressInfo.status);

              if (
                progressInfo.segment !== undefined &&
                progressInfo.total_segments !== undefined
              ) {
                setCurrentSegment(progressInfo.segment);
                setTotalSegments(progressInfo.total_segments);
              }

              if (progressInfo.file_path) {
                const audioUrl = `${API_BASE_URL}/download/${progressInfo.file_path.split("/").pop()}`;
                setAudioUrl(audioUrl);
                // 履歴に追加
                addToHistory(text, speakingRate, audioUrl);
                // 音声生成完了後、少し待ってから自動再生
                setTimeout(() => {
                  if (audioRef.current) {
                    audioRef.current.play().catch((error) => {
                      console.error("自動再生に失敗しました:", error);
                    });
                  }
                }, 500); // 0.5秒待機してからの再生で、音声ファイルの読み込みを待つ
              }
            } catch (parseError) {
              console.error("JSON解析エラー:", parseError);
            }
          }
        }
      }
    } catch (error: unknown) {
      if (error instanceof Error && error.name === "AbortError") {
        setStatusMessage("生成が中止されました");
      } else {
        const errorMessage =
          error instanceof Error ? error.message : "不明なエラーが発生しました";
        setError(`エラーが発生しました: ${errorMessage}`);
      }
    } finally {
      setIsGenerating(false);
      abortControllerRef.current = null;
    }
  };

  const handleGenerate = () => {
    if (!text.trim()) {
      setError("テキストを入力してください");
      return;
    }

    handleStreamingGenerate();
  };

  const handlePlayAudio = () => {
    if (audioRef.current) {
      audioRef.current.play();
    }
  };

  const handleDownload = () => {
    if (audioUrl) {
      const link = document.createElement("a");
      link.href = audioUrl;
      link.download = "synthesized_speech.wav";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  return (
    <Box sx={{ width: "100%", maxWidth: 800, mx: "auto" }}>
      {/* ヘッダー */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h4" component="h1" gutterBottom align="center">
            AI安野ボイス
          </Typography>
          <Typography variant="body1" color="text.secondary" align="center">
            テキストを安野たかひろの音声で読み上げます
          </Typography>
        </CardContent>
      </Card>

      {/* メイン入力エリア */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            <Settings sx={{ mr: 1, verticalAlign: "middle" }} />
            音声設定
          </Typography>
          <Box sx={{ mb: 3, mx: 4 }}>
            <Typography gutterBottom>
              話速: {speakingRate} ({getSpeakingRateLabel(speakingRate)})
            </Typography>
            <Slider
              value={speakingRate}
              onChange={handleSpeakingRateChange}
              min={10}
              max={30}
              step={1}
              marks={[
                { value: 10, label: "遅い" },
                { value: 15, label: "普通" },
                { value: 20, label: "速い" },
                { value: 30, label: "とても速い" },
              ]}
              disabled={isGenerating}
            />
          </Box>
          <Typography variant="h6" gutterBottom>
            <VolumeUp sx={{ mr: 1, verticalAlign: "middle" }} />
            テキスト入力
          </Typography>

          <Box sx={{ position: "relative", mb: 2 }}>
            <TextField
              fullWidth
              multiline
              rows={6}
              variant="outlined"
              placeholder="ここに音声化したいテキストを入力してください..."
              value={text}
              onChange={handleTextChange}
              disabled={isGenerating}
              sx={{ mb: 1 }}
            />
            {text && (
              <IconButton
                sx={{ position: "absolute", top: 8, right: 8 }}
                onClick={handleClearText}
                size="small"
              >
                <Clear />
              </IconButton>
            )}
          </Box>
          <Box sx={{ display: "flex", gap: 2, justifyContent: "center" }}>
            <Button
              variant="contained"
              size="large"
              startIcon={<PlayArrow />}
              onClick={handleGenerate}
              disabled={isGenerating || !text.trim()}
              sx={{ minWidth: 150 }}
            >
              音声生成
            </Button>

            {isGenerating && (
              <Button
                variant="outlined"
                size="large"
                startIcon={<Stop />}
                onClick={stopGeneration}
                color="error"
              >
                停止
              </Button>
            )}
          </Box>
        </CardContent>
      </Card>

      {/* 履歴セクション */}
      {history.length > 0 && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                mb: 2,
              }}
            >
              <Typography variant="h6">
                <History sx={{ mr: 1, verticalAlign: "middle" }} />
                履歴
              </Typography>
              <Button
                onClick={() => setShowHistory(!showHistory)}
                endIcon={showHistory ? <ExpandLess /> : <ExpandMore />}
                size="small"
              >
                {showHistory ? "非表示" : "表示"} ({history.length}件)
              </Button>
            </Box>

            <Collapse in={showHistory}>
              <List dense>
                {history.map((item, index) => (
                  <React.Fragment key={item.id}>
                    <ListItem>
                      <ListItemText
                        primary={item.text}
                        secondary={
                          <Box sx={{ display: "flex", gap: 1, mt: 1 }}>
                            <Chip
                              label={`話速: ${item.speakingRate}`}
                              size="small"
                              variant="outlined"
                            />
                            <Chip
                              label={item.timestamp.toLocaleString()}
                              size="small"
                              variant="outlined"
                            />
                            {item.audioUrl && (
                              <Chip
                                label="音声あり"
                                size="small"
                                color="success"
                                variant="outlined"
                              />
                            )}
                          </Box>
                        }
                      />
                      <ListItemSecondaryAction>
                        <Box sx={{ display: "flex", gap: 1 }}>
                          <Button
                            size="small"
                            onClick={() => selectFromHistory(item)}
                            disabled={isGenerating}
                          >
                            選択
                          </Button>
                          {item.audioUrl && (
                            <Button
                              size="small"
                              color="success"
                              onClick={() => {
                                setAudioUrl(item.audioUrl);
                                handlePlayAudio();
                              }}
                              disabled={isGenerating}
                            >
                              再生
                            </Button>
                          )}
                          <IconButton
                            size="small"
                            onClick={() => removeFromHistory(item.id)}
                            color="error"
                          >
                            <Delete />
                          </IconButton>
                        </Box>
                      </ListItemSecondaryAction>
                    </ListItem>
                    {index < history.length - 1 && <Divider />}
                  </React.Fragment>
                ))}
              </List>
            </Collapse>
          </CardContent>
        </Card>
      )}

      {/* 進捗表示 */}
      {isGenerating && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              生成進捗
            </Typography>

            <LinearProgress
              variant="determinate"
              value={progress}
              sx={{ mb: 2, height: 8, borderRadius: 4 }}
            />

            <Typography variant="body2" color="text.secondary">
              {statusMessage}
              {currentSegment !== null && totalSegments !== null && (
                <span>
                  (セグメント {currentSegment}/{totalSegments})
                </span>
              )}
            </Typography>

            <Typography variant="body2" color="primary">
              {progress.toFixed(1)}% 完了
            </Typography>
          </CardContent>
        </Card>
      )}

      {/* エラー表示 */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* 音声プレイヤー */}
      {audioUrl && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              生成された音声
            </Typography>

            <Box
              sx={{
                display: "flex",
                gap: 2,
                alignItems: "center",
                flexWrap: "wrap",
              }}
            >
              <Button
                variant="contained"
                startIcon={<PlayArrow />}
                onClick={handlePlayAudio}
                color="success"
              >
                再生
              </Button>

              <Button
                variant="outlined"
                startIcon={<Download />}
                onClick={handleDownload}
              >
                ダウンロード
              </Button>
            </Box>

            <audio
              ref={audioRef}
              src={audioUrl}
              controls
              style={{ width: "100%", marginTop: "16px" }}
            />
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default TTSInterface;

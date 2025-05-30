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
  Divider,
  Collapse,
  Chip,
} from "@mui/material";
import {
  PlayArrow,
  Stop,
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
  text: string;
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
  const [text, setText] = useState(
    "テクノロジーで誰も取り残さない日本へ。チームみらいはテクノロジーで政治をかえる。あなたと一緒に未来をつくる。"
  );
  const [speakingRate, setSpeakingRate] = useState(18);
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [currentSegment, setCurrentSegment] = useState<number | null>(null);
  const [totalSegments, setTotalSegments] = useState<number | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);

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
    fullText: string,
    speakingRate: number,
    audioUrl: string | null
  ) => {
    const newItem: HistoryItem = {
      id: Date.now().toString(),
      text,
      fullText,
      speakingRate,
      audioUrl,
      timestamp: new Date(),
    };

    const newHistory = [newItem, ...history].slice(0, 20); // 最新20件まで保持
    setHistory(newHistory);
    saveHistoryToStorage(newHistory);
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
                addToHistory(progressInfo.text, text, speakingRate, audioUrl);
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

  return (
    <Box sx={{ width: "100%" }}>
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
              max={25}
              step={1}
              marks={[
                { value: 10, label: "遅い" },
                { value: 15, label: "普通" },
                { value: 20, label: "速い" },
                { value: 25, label: "とても速い" },
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
                  <HistoryItemComponent
                    key={item.id}
                    item={item}
                    index={index}
                    onRemove={removeFromHistory}
                  />
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
    </Box>
  );
};

export default TTSInterface;

interface HistoryItemComponentProps {
  item: HistoryItem;
  index: number;
  onRemove: (id: string) => void;
}

const HistoryItemComponent: React.FC<HistoryItemComponentProps> = ({
  item,
  index,
  onRemove,
}) => {
  const audioRef = useRef<HTMLAudioElement>(null);

  return (
    <>
      <ListItem>
        <Box
          sx={{
            width: "100%",
          }}
        >
          <Box
            display="flex"
            sx={{
              width: "100%",
            }}
          >
            <Box sx={{ width: "100%" }}>
              <ListItemText primary={item.text} />
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
            </Box>
            <Box sx={{ display: "flex", gap: 1 }}>
              <IconButton
                size="small"
                onClick={() => onRemove(item.id)}
                color="error"
              >
                <Delete />
              </IconButton>
            </Box>
          </Box>
          {item.audioUrl && (
            <audio
              ref={audioRef}
              src={item.audioUrl}
              controls
              style={{ width: "100%", marginTop: "16px" }}
            />
          )}
        </Box>
      </ListItem>
      {index < history.length - 1 && <Divider />}
    </>
  );
};

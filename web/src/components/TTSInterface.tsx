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
  sessionId: string; // 同じ音声生成セッションのアイテムをグループ化するためのID
  text: string;
  fullText: string; // 完全なテキストを保存
  speakingRate: number;
  audioUrl: string | null;
  timestamp: Date;
  segment?: number;
  totalSegments?: number;
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
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);

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
    audioUrl: string | null,
    segment?: number,
    totalSegments?: number
  ) => {
    // currentSessionId が null の場合は新しいセッションIDを生成
    const sessionId = currentSessionId || Date.now().toString();
    if (!currentSessionId) {
      console.log("新しいセッションIDを自動生成します:", sessionId);
      setCurrentSessionId(sessionId);
    }

    const newItem: HistoryItem = {
      id: Date.now().toString(),
      sessionId: sessionId, // 自動生成されたIDを使用
      text,
      fullText,
      speakingRate,
      audioUrl,
      timestamp: new Date(),
      segment,
      totalSegments,
    };

    setHistory((prevHistory) => {
      // まず、現在のセッションのアイテムを全て抽出
      const currentSessionItems = prevHistory.filter(
        (item) => item.sessionId === sessionId
      );

      // 他のセッションのアイテム
      const otherSessionItems = prevHistory.filter(
        (item) => item.sessionId !== sessionId
      );

      let allSessionItems;

      if (currentSessionItems.length > 0) {
        // 同じセッションの他のアイテムがある場合、それらのリストに新しいアイテムを追加
        // セグメント番号で順序を保証
        const updatedSessionItems = [...currentSessionItems];

        // 適切な位置に挿入（セグメント番号が小さい順）
        const insertIndex = updatedSessionItems.findIndex(
          (item) => (item.segment || 0) > (newItem.segment || 0)
        );

        if (insertIndex === -1) {
          // 最後に追加
          updatedSessionItems.push(newItem);
        } else {
          // 指定位置に挿入
          updatedSessionItems.splice(insertIndex, 0, newItem);
        }

        // 現在のセッションを先頭に、他のセッションをその後に
        allSessionItems = [...updatedSessionItems, ...otherSessionItems];
      } else {
        // 新しいセッションの場合は先頭に追加
        allSessionItems = [newItem, ...otherSessionItems];
      }

      // 最大50件まで保存
      const updatedHistory = allSessionItems.slice(0, 50);
      saveHistoryToStorage(updatedHistory);
      return updatedHistory;
    });
  };

  // 履歴アイテムを削除
  const removeFromHistory = (id: string) => {
    const newHistory = history.filter((item) => item.id !== id);
    setHistory(newHistory);
    saveHistoryToStorage(newHistory);
  };

  // セッション全体を削除
  const removeSessionFromHistory = (sessionId: string) => {
    const newHistory = history.filter((item) => item.sessionId !== sessionId);
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
    setCurrentSessionId(null); // セッションIDをクリア
  };

  const handleStreamingGenerate = async () => {
    setIsGenerating(true);
    setProgress(0);
    setStatusMessage("音声生成を開始しています...");
    setError(null);
    setCurrentSegment(null);
    setTotalSegments(null);

    // 新しいセッションIDを生成
    const newSessionId = Date.now().toString();
    console.log("新しいセッションを開始します:", newSessionId);
    setCurrentSessionId(newSessionId);

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
                addToHistory(
                  progressInfo.text,
                  text,
                  speakingRate,
                  audioUrl,
                  progressInfo.segment,
                  progressInfo.total_segments
                );
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
      // 注意: ここでセッションIDをクリアしないことで、
      // 同じリクエストの複数のセグメントが正しく同じセッションIDを保持できます
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
        {isGenerating && (
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
        )}
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
                {showHistory ? "非表示" : "表示"} (
                {
                  // セッション数をカウント（重複を除く）
                  new Set(history.map((item) => item.sessionId)).size
                }
                件)
              </Button>
            </Box>

            <Collapse in={showHistory}>
              <List>
                {/* セッションIDでグループ化して重複を避ける */}
                {(() => {
                  // 一意のセッションIDを取得
                  const uniqueSessionIds = Array.from(
                    new Set(history.map((item) => item.sessionId))
                  );

                  // タイムスタンプで新しい順にセッションをソート
                  return (
                    uniqueSessionIds
                      .map((sessionId) => {
                        // 同じセッションのアイテムを取得
                        const sessionItems = history.filter(
                          (item) => item.sessionId === sessionId
                        );
                        // セグメント番号でソート
                        return sessionItems.sort(
                          (a, b) => (a.segment || 0) - (b.segment || 0)
                        );
                      })
                      // セッションの作成日時で新しい順にソート
                      .sort((a, b) => {
                        if (!a.length || !b.length) return 0;
                        return (
                          new Date(b[0].timestamp).getTime() -
                          new Date(a[0].timestamp).getTime()
                        );
                      })
                      .map((sessionItems) => {
                        if (!sessionItems.length) return null;
                        const sessionId = sessionItems[0].sessionId;
                        return (
                          <SessionHistoryItem
                            key={sessionId}
                            sessionItems={sessionItems}
                            onRemove={removeFromHistory}
                            onRemoveSession={removeSessionFromHistory}
                          />
                        );
                      })
                  );
                })()}
              </List>
            </Collapse>
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

interface SessionHistoryItemProps {
  sessionItems: HistoryItem[];
  onRemove: (id: string) => void;
  onRemoveSession: (sessionId: string) => void;
}

const SessionHistoryItem: React.FC<SessionHistoryItemProps> = ({
  sessionItems,
  onRemoveSession,
}) => {
  const [expanded, setExpanded] = useState(false);

  // セッションの最初のアイテム
  const firstItem = sessionItems[0];
  const hasMultipleItems = sessionItems.length > 1;

  // セッション内のすべてのアイテムを削除
  const handleRemoveSession = () => {
    // セッション全体を一括で削除
    if (sessionItems[0]) {
      onRemoveSession(sessionItems[0].sessionId);
    }
  };

  return (
    <Box
      sx={{
        mb: 2,
        bgcolor: "rgba(0, 0, 0, 0.02)",
        borderRadius: 1,
        overflow: "hidden",
      }}
    >
      {/* セッションヘッダー */}
      <ListItem>
        <Box sx={{ width: "100%" }}>
          <Box
            display="flex"
            sx={{
              width: "100%",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <Typography variant="subtitle1">
              {new Date(firstItem.timestamp).toLocaleDateString()}{" "}
              {new Date(firstItem.timestamp).toLocaleTimeString()}
            </Typography>
            {hasMultipleItems && (
              <Button
                size="small"
                onClick={() => setExpanded(!expanded)}
                endIcon={expanded ? <ExpandLess /> : <ExpandMore />}
              >
                {expanded ? "折りたたむ" : "すべて表示"} ({sessionItems.length}
                セグメント)
              </Button>
            )}
            <Box sx={{ display: "flex", gap: 1 }}>
              <IconButton
                size="small"
                onClick={handleRemoveSession}
                color="error"
              >
                <Delete />
              </IconButton>
            </Box>
          </Box>

          <Box sx={{ mt: 1 }}>
            <Typography variant="body2" color="text.secondary">
              原文:
            </Typography>
            <Typography variant="body1">{firstItem.fullText}</Typography>
            <Box sx={{ display: "flex", gap: 1, mt: 1 }}>
              <Chip
                label={`話速: ${firstItem.speakingRate}`}
                size="small"
                variant="outlined"
              />
              <Chip
                label={`${sessionItems.length}セグメント`}
                size="small"
                variant="outlined"
                color="primary"
              />
            </Box>
          </Box>
        </Box>
      </ListItem>

      {/* 最初のセグメントは常に表示 */}
      <ListItem sx={{ bgcolor: "rgba(0, 0, 0, 0.01)", pl: 4 }}>
        <Box sx={{ width: "100%" }}>
          <Typography variant="caption" color="text.secondary">
            セグメント {firstItem.segment || 1}/
            {firstItem.totalSegments || sessionItems.length}
          </Typography>
          <ListItemText primary={firstItem.text} />
          {firstItem.audioUrl && (
            <audio
              src={firstItem.audioUrl}
              controls
              style={{ width: "100%", marginTop: "8px" }}
            />
          )}
        </Box>
      </ListItem>

      {/* 残りのセグメント（展開時のみ表示） */}
      {expanded &&
        sessionItems.slice(1).map((item) => (
          <ListItem
            key={item.id}
            sx={{ bgcolor: "rgba(0, 0, 0, 0.01)", pl: 4 }}
          >
            <Box sx={{ width: "100%" }}>
              <Typography variant="caption" color="text.secondary">
                セグメント {item.segment || sessionItems.indexOf(item) + 1}/
                {item.totalSegments || sessionItems.length}
              </Typography>
              <ListItemText primary={item.text} />
              {item.audioUrl && (
                <audio
                  src={item.audioUrl}
                  controls
                  style={{ width: "100%", marginTop: "8px" }}
                />
              )}
            </Box>
          </ListItem>
        ))}

      <Divider />
    </Box>
  );
};

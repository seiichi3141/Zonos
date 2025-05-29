"use client";

import React, { useState, useRef } from "react";
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
} from "@mui/material";
import {
  PlayArrow,
  Stop,
  Download,
  VolumeUp,
  Settings,
  Clear,
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

  const audioRef = useRef<HTMLAudioElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

              if (progressInfo.file_path && progressInfo.progress === 100) {
                const audioUrl = `${API_BASE_URL}/download/${progressInfo.file_path.split("/").pop()}`;
                setAudioUrl(audioUrl);
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
        </CardContent>
      </Card>

      {/* 設定エリア */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            <Settings sx={{ mr: 1, verticalAlign: "middle" }} />
            音声設定
          </Typography>

          <Box sx={{ mb: 3 }}>
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
        </CardContent>
      </Card>

      {/* 生成ボタン */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
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
                  {" "}
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

import { Card, CardContent, Container, Typography } from "@mui/material";
import TTSInterface from "../components/TTSInterface";

export default function Home() {
  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
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
      <TTSInterface />
    </Container>
  );
}

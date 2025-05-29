import { Container } from "@mui/material";
import TTSInterface from "../components/TTSInterface";

export default function Home() {
  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <TTSInterface />
    </Container>
  );
}

import React, { useState, useEffect } from 'react';
import type { LocalJSXCommandCall } from '../../types/command.js';
import { Box, Text, Newline } from '../../ink.js';
import { useAppState } from '../../state/AppState.js';
import { PressEnterToContinue } from '../../components/PressEnterToContinue.js';
import { Spinner } from '../../components/Spinner.js';

export const call: LocalJSXCommandCall = (onDone, _context, _args) => {
  return Promise.resolve(<Diagnose onDone={onDone} />);
};

function Diagnose({ onDone }: { onDone: () => void }) {
  const [ollamaStatus, setOllamaStatus] = useState<'checking' | 'ok' | 'fail'>('checking');
  const [bridgeStatus, setBridgeStatus] = useState<'checking' | 'ok' | 'fail'>('checking');
  const mcpServers = useAppState(s => s.mcp.servers);

  useEffect(() => {
    async function check() {
      // Check Ollama
      try {
        const resp = await fetch('http://localhost:11434/api/tags');
        setOllamaStatus(resp.ok ? 'ok' : 'fail');
      } catch {
        setOllamaStatus('fail');
      }

      // Check Bridge
      setBridgeStatus(Object.keys(mcpServers).includes('review-bridge') ? 'ok' : 'fail');
    }
    check();
  }, [mcpServers]);

  return (
    <Box flexDirection="column" padding={1}>
      <Text bold>System Diagnosis</Text>
      <Newline />

      <Box gap={1}>
        <Text>Ollama Backend:</Text>
        {ollamaStatus === 'checking' && <Text dimColor>Checking...</Text>}
        {ollamaStatus === 'ok' && <Text color="green">Running</Text>}
        {ollamaStatus === 'fail' && <Text color="red">Not Found (ensure Ollama is running on port 11434)</Text>}
      </Box>

      <Box gap={1}>
        <Text>Review Bridge (Python MCP):</Text>
        {bridgeStatus === 'checking' && <Text dimColor>Checking...</Text>}
        {bridgeStatus === 'ok' && <Text color="green">Connected</Text>}
        {bridgeStatus === 'fail' && <Text color="red">Disconnected (ensure Python bridge is configured correctly)</Text>}
      </Box>

      <Newline />
      {ollamaStatus === 'ok' && bridgeStatus === 'ok' ? (
        <Text color="green">All systems operational. Ready for manuscript review.</Text>
      ) : (
        <Text color="yellow">Some systems are not ready. Review capabilities may be limited.</Text>
      )}

      <Newline />
      <PressEnterToContinue />
    </Box>
  );
}

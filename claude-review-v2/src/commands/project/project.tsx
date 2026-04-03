import React from 'react';
import type { LocalJSXCommandCall } from '../../types/command.js';
import { Box, Text, Newline } from '../../ink.js';
import { useAppState } from '../../state/AppState.js';
import { PressEnterToContinue } from '../../components/PressEnterToContinue.js';

export const call: LocalJSXCommandCall = (onDone, _context, _args) => {
  return Promise.resolve(<ProjectStatus onDone={onDone} />);
};

function ProjectStatus({ onDone }: { onDone: () => void }) {
  const mcpServers = useAppState(s => s.mcp.servers);
  const bridgeConnected = Object.keys(mcpServers).includes('review-bridge');

  return (
    <Box flexDirection="column" padding={1} borderStyle="round" borderColor="blue">
      <Text bold color="blue">Manuscript Project Status</Text>
      <Newline />
      <Box flexDirection="column">
        <Text>Bridge Connection: {bridgeConnected ? <Text color="green">Connected</Text> : <Text color="red">Disconnected</Text>}</Text>
        <Text dimColor>Use /diagnose if the bridge is not connected.</Text>
      </Box>
      <Newline />
      <Box flexDirection="column">
        <Text bold>Next steps:</Text>
        <Text>1. Ensure your manuscript (.docx or .pdf) is in the current directory.</Text>
        <Text>2. Run <Text color="cyan">/review</Text> to start the analysis.</Text>
        <Text>3. Use <Text color="cyan">/artifacts</Text> to see generated reports.</Text>
      </Box>
      <Newline />
      <PressEnterToContinue />
    </Box>
  );
}

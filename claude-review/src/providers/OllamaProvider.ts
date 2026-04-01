import { LLMProvider, ChatMessage, ChatOptions } from './LLMProvider';
import { EventLogger } from '../logging/EventLogger';
import axios from 'axios';

export class OllamaProvider extends LLMProvider {
  constructor(baseURL: string, defaultModel: string, logger: EventLogger) {
    super('no-key', baseURL, defaultModel, logger);
  }

  public override async chat(messages: ChatMessage[], options: ChatOptions = {}): Promise<string> {
    const startTime = Date.now();
    const model = options.model || (this as any).defaultModel;
    const url = `${(this as any).client.baseURL}/chat`;
    
    try {
      const response = await axios.post(url, {
        model,
        messages,
        stream: false,
        options: {
          temperature: options.temperature ?? 0.1,
          num_predict: options.max_tokens,
        }
      });

      const duration = Date.now() - startTime;
      const content = response.data.message?.content || '';

      (this as any).logger.logNetwork({
        destination: url,
        purpose: 'chat/completions (ollama)',
        status: response.status,
        duration,
        timestamp: Date.now(),
        model
      });

      return content;
    } catch (error: any) {
      const duration = Date.now() - startTime;
      const status = error.response?.status || 500;
      
      (this as any).logger.logNetwork({
        destination: url,
        purpose: 'chat/completions (ollama)',
        status,
        duration,
        timestamp: Date.now(),
        model
      });
      
      console.warn(`[backend] ollama | endpoint failed. Ensure ollama serve is running.`);
      throw error;
    }
  }

  public override async *streamChat(messages: ChatMessage[], options: ChatOptions = {}): AsyncGenerator<string> {
    const startTime = Date.now();
    const model = options.model || (this as any).defaultModel;
    const url = `${(this as any).client.baseURL}/chat`;

    try {
      const response = await axios.post(url, {
        model,
        messages,
        stream: true,
        options: {
          temperature: options.temperature ?? 0.1,
          num_predict: options.max_tokens,
        }
      }, {
        responseType: 'stream'
      });

      let fullContent = '';
      for await (const chunk of response.data) {
        const lines = chunk.toString().split('\n').filter(Boolean);
        for (const line of lines) {
          try {
            const data = JSON.parse(line);
            if (data.message?.content) {
              fullContent += data.message.content;
              yield data.message.content;
            }
          } catch (e) {
            // ignore JSON parse error on incomplete chunks
          }
        }
      }

      const duration = Date.now() - startTime;
      (this as any).logger.logNetwork({
        destination: url,
        purpose: 'chat/completions (ollama stream)',
        status: response.status,
        duration,
        timestamp: Date.now(),
        model
      });
    } catch (error: any) {
      const duration = Date.now() - startTime;
      const status = error.response?.status || 500;
      
      (this as any).logger.logNetwork({
        destination: url,
        purpose: 'chat/completions (ollama stream)',
        status,
        duration,
        timestamp: Date.now(),
        model
      });
      
      console.warn(`[backend] ollama | streaming endpoint failed. Ensure ollama serve is running.`);
      throw error;
    }
  }
}

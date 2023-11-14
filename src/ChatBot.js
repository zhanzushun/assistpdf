import React, { useState, useEffect } from 'react';

import ReactMarkdown from 'react-markdown';
import { Light as SyntaxHighlighter } from 'react-syntax-highlighter';
import { docco } from 'react-syntax-highlighter/dist/esm/styles/hljs';
import './ChatBot.css'
import { getLocalStorage, emptyString } from './Util';
import { FileUpload } from './FileUpload';
import { API_HOST_PORT, API_PREFIX } from './Consts';
import axios from 'axios';


import { python } from 'react-syntax-highlighter/dist/esm/languages/hljs';
SyntaxHighlighter.registerLanguage('python', python);


const components = {
  code({ node, inline, className, children, ...props }) {
    const match = /language-(\w+)/.exec(className || '');
    const language = match && match[1] ? match[1] : 'javascript';
    return !inline && language ? (
      <SyntaxHighlighter language={language} style={docco} PreTag="div" customStyle={{ fontSize: '14px', backgroundColor: '#f6f6f6' }} {...props}>
        {String(children).replace(/\n$/, '')}
      </SyntaxHighlighter>
    ) : (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },
};


const ChatMessage = ({ message, sender }) => {
  return (
    <div className={`chat-message ${sender}`}>
      <div className="message-bubble">
        <ReactMarkdown components={components} children={message} />
      </div>
      <div className="message-time">{new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
    </div>
  );
};


const fetchSendMessage = async (userInput, fileIdList, onResponseWord) => {

  let user = getLocalStorage('user')
  if (emptyString(user)){
    user = getLocalStorage('unionId') + (new Date().toISOString().slice(0, 10).replace(/-/g, ''))
  }

  var body = {
    user,
    prompt: userInput,
    local_file_list: fileIdList
  }

  var ask_url = `${API_HOST_PORT}/${API_PREFIX}/ask`
  const response = await axios.post(ask_url, body);
  console.log('upload.response=' + JSON.stringify(response.data))
  if ('task_id' in response.data){
    const task_id = response.data.task_id;
    const es = new EventSource(`${API_HOST_PORT}/${API_PREFIX}/status/${task_id}`);
    es.onmessage = (event) => {
        console.log(event.data)
        if (event.data === 'done') {
            axios.get(`${API_HOST_PORT}/${API_PREFIX}/task_result/${task_id}`).then(response2 => {
                console.log(response2.data);
                onResponseWord(response2.data, true)
            })
            es.close();
        }
        else if (event.data === 'in_progress' || event.data === 'queued') {
          onResponseWord('.', false)
        }
        else {
          onResponseWord(event.data, false)
        }
    };
  }
  else if ('filename' in response.data){
    window.alert('该文件已存在: ' + response.data.uploadtime + " " + response.data.filename)
  }
}

const ChatInput = ({ onSend }) => {
  const [inputValue, setInputValue] = useState('');

  const handleAskDoc = () => {
    if (inputValue.trim()) {
      onSend(inputValue);
      setInputValue('');
    }
  };

  const vipBtnClass = 'button-vip'
  return (
    <div className="chat-input-container">
      <textarea
        className="chat-input"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
      />
      <div className={`button ${vipBtnClass} send-button`} onClick={handleAskDoc}>
        文档问答
      </div>
    </div>
  );
};

const ChatBot = () => {

  const [messages, setMessages] = useState([]);
  const [fileIdList, setFileIdList] = useState('')

  useEffect(() => {
    if (document.body.scrollHeight <= window.innerHeight || messages.length === 0){
        return
    }
    window.scrollTo({
      top: document.body.scrollHeight - window.innerHeight + 20,
      behavior: 'smooth',
    });
  }, [messages]);

  const addMessage = (message, sender) => {
    setMessages((prevMessages) => [...prevMessages, { message, sender }]);
  };
  const updateMessage = (message, sender) => {
    setMessages((prevMessages) => [...prevMessages.slice(0, prevMessages.length - 1), { message, sender }]);
  };

  const handleSendMessage = async (input) => {
    if (!input) return;
    addMessage(input, 'sent');
    let botResponse = '';
    await fetchSendMessage(input, fileIdList, (word, reset) => {
      if (botResponse === '') {
        botResponse += word
        if (reset) botResponse = word
        addMessage(word, 'received')
      }
      else {
        botResponse += word;
        if (reset) botResponse = word
        updateMessage(botResponse, 'received');
      }
    });
  };

  const handleFileIdList = (fileIdList) => {
    console.log('fileIdList=' + JSON.stringify(fileIdList))
    setFileIdList(fileIdList)
  }

  return (
    <div className="app-container">
      <div className="chat-section">
        <div className="chat-container">
          {messages.map((msg, index) => (
            <ChatMessage key={index} message={msg.message} sender={msg.sender} />
          ))}
        </div>
        <ChatInput onSend={handleSendMessage} />
      </div>
      <FileUpload onFileIdList={handleFileIdList}/>
    </div>)
};

export default ChatBot;

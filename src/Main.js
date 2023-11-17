import React from 'react';

import ChatBot from './ChatBot'

const Main = () => {

  return (
    <div>
        <div className="title-container">
          <h1 className="title"><span style={{ cursor: 'pointer' }}>🤖 OPENAI - ASSISTANT 2</span></h1>
        </div>

      <ChatBot />
    </div>)
};

export default Main;

import React from 'react';
import ReactDOM from 'react-dom/client';
import { RecordingDetailsApp } from './RecordingDetailsApp';
import '../popup/App.css';
import './recording-details.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RecordingDetailsApp />
  </React.StrictMode>
);

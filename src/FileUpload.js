import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './FileUpload.css'
import { API_HOST_PORT, API_PREFIX } from './Consts';

export const FileUpload = ({ onFileIdList }) => {
  // State for storing the list of uploaded files
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [doing, setDoing] = useState(false);
  const [message, setMessage] = useState('点这里上传文件');

  const handleFileUpload = async (event) => {
    let formData = new FormData();
    for (let file of event.target.files) {
      formData.append('files', file);
    }
    try {
      setMessage('上传文件中...')
      setDoing(true)
      const response = await axios.post(`${API_HOST_PORT}/${API_PREFIX}/upload_file`, formData);
      console.log('upload.response=' + JSON.stringify(response.data))
      var local_file_id = response.data['local_file_id']
      window.alert('文件上传成功: ' + local_file_id)
      fetchUploadedFiles()
    } catch (error) {
      window.alert('文件上传失败, 详细信息:' + JSON.stringify(error))
      console.error("Error during the POST request:", error);
    }
    setMessage('点这里上传文件')
    setDoing(false)
  };

  const fetchUploadedFiles = () => {
    axios.post(`${API_HOST_PORT}/${API_PREFIX}/file_list`)
      .then(response => {
        setUploadedFiles(response.data);
      })
      .catch((error) => {
        console.error('Error:', error);
      });
  };

  const handleFileSelection = (event, file_id) => {
    if (event.target.checked) {
      if (selectedFiles.length >= 10) {
        window.alert('目前只支持最多选择10个文档')
        return
      }
      setSelectedFiles(prevSelected => [...prevSelected, file_id])
    } else {
      setSelectedFiles(prevSelected => prevSelected.filter(t => t !== file_id))
    }
  };

  // Fetch the list of uploaded files when the component is mounted
  useEffect(() => {
    fetchUploadedFiles();
  }, []);

  useEffect(() => {
    onFileIdList(selectedFiles);
  }, [selectedFiles, onFileIdList]);

  return (
    <div className="file-upload-container">
      {/* Button for uploading files */}
      { doing &&
        <div>处理中...</div>
      }
      { !doing && 
      <div className='button button-nonvip' onClick={() => document.getElementById('fileInput').click()}>
        {message}<br/>(耐心等待)</div>
      }

      <input type="file" id="fileInput" multiple onChange={handleFileUpload} style={{ display: 'none' }} />
      <div className="small-font">.pdf, .docx, .doc, .ppt, .pptx, .txt</div>

      {/* Section for document library */}
      <h2>文档库</h2>
      <ul className="file-list small-font">
        {uploadedFiles.map((file, index) =>
          <li key={index}>
            <input type="checkbox" value={file.selected} onChange={event => handleFileSelection(event, file.local_file_id)} />
            <span><a href={file.url} target='_blank' rel="noreferrer">{file.original_file_name}</a></span>
          </li>
        )}
      </ul>
    </div>
  );
};

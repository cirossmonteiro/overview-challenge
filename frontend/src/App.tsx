import { Form, Input, Table } from 'antd';
import axios from 'axios';
import * as fabric from 'fabric'; // v6
import { useEffect, useRef, useState } from 'react';

import reactLogo from './assets/react.svg';
import viteLogo from '/vite.svg';
import './App.css';

// video thumbnail: https://commandcodes.medium.com/how-to-capture-video-thumbnails-using-javascript-a-javascript-developers-guide-6b2cc4d5a498

const COLUMNS = [
  {
    title: "IoU",
    dataIndex: "iou"
  },
  {
    title: "Confidence",
    dataIndex: "confidence"
  },
  {
    title: "Base64 length",
    dataIndex: "b64"
  },
  {
    title: "Response",
    dataIndex: "response",
    render: JSON.stringify
  }

]

function App() {
  // states
  const [base64, setBase64]             = useState("");
  const [confidence, setConfidence]     = useState<number>(0.4); // originally 0.7
  const [dimensions, setDimensions]     = useState<any>(null);
  const [iou, setIou]                   = useState<number>(0.5);
  const [response, setResponse]         = useState<Object>({});
  const [timeInterval, setTimeInterval] = useState(1000);
  const [predictions, setPredictions]   = useState<any[]>([]);
  
  // refs
  const canvasEl = useRef<HTMLCanvasElement>(null);
  const context  = useRef<CanvasRenderingContext2D | null>(null);
  const interval = useRef<number>(-1);
  const videoEl  = useRef<HTMLVideoElement>(null);

  // get video dimensions
  useEffect(() => {
    if (videoEl.current) {
      videoEl.current.onloadedmetadata = () => {
        setDimensions({
          width: videoEl.current?.videoWidth || 0,
          height: videoEl.current?.videoHeight || 0
        });
      }
    }
  }, []);

  // draw the Fabric canvas according to video dimensions
  useEffect(() => {
    if (canvasEl.current && dimensions) {
      const canvas = new fabric.Canvas(canvasEl.current, dimensions);
      canvas.backgroundColor = "red";
      canvas.renderAll();
      context.current = canvas.getContext();
    }
  }, [dimensions]);

  // copy the frame from video to Fabric canvas
  useEffect(() => {
    if (context.current && videoEl.current && dimensions) {
      if (interval.current !== -1) {
        clearInterval(interval.current);
      }
      interval.current = setInterval(() => {
        if (videoEl.current){
          context.current?.drawImage(videoEl.current, 0, 0, dimensions.width, dimensions.height);
          setBase64(canvasEl.current?.toDataURL("image/jpeg") || "");
        }
      }, timeInterval);
    }
    return () => {
      if (interval.current !== -1) {
        clearInterval(interval.current);
      }
    }
  }, [dimensions, timeInterval]);

  // request to API
  useEffect(() => {
    (async () => {
      if (base64) {
        const response = await axios.post("http://localhost:5000/detect", {
          iou, confidence, base64,
          image_path: "ciro_test"
        });
        setResponse(response.data);
        setPredictions(p => [ ...p, {
          iou, confidence,
          b64: base64.length,
          response: response.data
        }]);
      }
    })()
  }, [base64, iou, confidence]);

  const data: any[] = predictions.length > 10 ? predictions.slice(-10) : predictions;

  return (
    <>
      <div>
        <a href="https://vite.dev" target="_blank">
          <img src={viteLogo} className="logo" alt="Vite logo" />
        </a>
        <a href="https://react.dev" target="_blank">
          <img src={reactLogo} className="logo react" alt="React logo" />
        </a>
      </div>
      <h1>Vite + React</h1>
      <div className="card">
        <video controls ref={videoEl} crossOrigin="anonymous">
          <source src="https://fabricjs.com/site_assets/dizzy.mp4" />
        </video>
        <canvas ref={canvasEl}/>
        <Form>

          <Form.Item label="Time interval">
            <Input value={timeInterval} type="number"
              onChange={e => setTimeInterval(parseInt(e.target.value))} />
          </Form.Item>

          <Form.Item label="IoU">
            <Input value={iou} type="number" min={0}
              onChange={e => setIou(parseFloat(e.target.value))} />
          </Form.Item>

          <Form.Item label="Confidence">
            <Input value={confidence} type="number" min={0}
              onChange={e => setConfidence(parseFloat(e.target.value))} />
          </Form.Item>

          <Form.Item label="Algorithm's response">
            <Input.TextArea value={JSON.stringify(response)} rows={10}  />
          </Form.Item>

        </Form>
        {/* <div>{JSON.stringify(response)}</div> */}
        <Table columns={COLUMNS} dataSource={data} />
      </div>
      <p className="read-the-docs">
        Click on the Vite and React logos to learn more
      </p>
    </>
  )
}

export default App

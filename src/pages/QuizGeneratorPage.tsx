import { useState, useRef } from 'react';
import Header from '../components/layout/Header';
import { Card, Button, Badge } from '../components/ui/UIComponents';
import { useApp } from '../store/AppContext';
import { QuizQuestion } from '../types';
import { apiGenerateQuiz, apiGenerateQuizFromFile } from '../services/api';
import { Brain, Upload, FileText, Check, X, RotateCcw, AlertTriangle, Edit3, Trash2 } from 'lucide-react';
import { useStagger } from '../hooks/useStagger';

const SAMPLE_TEXT = `Official statistics form the backbone of evidence-based policy making in India. The National Statistical Office (NSO) conducts large-scale surveys including the National Sample Survey (NSS) to collect data on various socio-economic indicators. Survey design involves careful planning of sampling frames, sample size determination, and questionnaire development. Data quality assurance is critical and involves validation, verification, and reconciliation processes. Python programming has become essential for data analysis in government statistical offices, enabling automation of data processing pipelines. SQL databases are used to store and manage large volumes of statistical data. Data visualization tools like Power BI help create interactive dashboards for policy makers. Artificial Intelligence and Machine Learning techniques are increasingly being applied to official statistics for predictive analytics and anomaly detection. Data privacy is governed by the Digital Personal Data Protection Act (DPDP) which sets guidelines for handling citizen data. Cybersecurity measures are essential to protect sensitive government data from unauthorized access.`;

export default function QuizGeneratorPage() {
  const { saveQuiz } = useApp();
  const { animate, staggerStyle } = useStagger();
  const [inputMethod, setInputMethod] = useState<'paste' | 'upload'>('paste');
  const [text, setText] = useState('');
  const [questionCount, setQuestionCount] = useState(5);
  const [difficulty, setDifficulty] = useState('Medium');
  const [generating, setGenerating] = useState(false);
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [inQuiz, setInQuiz] = useState(false);
  const [answers, setAnswers] = useState<(number | null)[]>([]);
  const [submitted, setSubmitted] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState('');
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [fileName, setFileName] = useState('');
  const [generatedBy, setGeneratedBy] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleGenerate = async () => {
    setGenerating(true);
    await new Promise(r => setTimeout(r, 800));
    try {
      if (inputMethod === 'upload' && uploadedFile) {
        const ext = (uploadedFile.name.split('.').pop() || '').toLowerCase();
        if (['pdf', 'docx', 'pptx', 'ppt'].includes(ext)) {
          // real text extraction on the backend
          const generated = await apiGenerateQuizFromFile(uploadedFile, questionCount, difficulty);
          setQuestions(generated.questions);
          setAnswers(new Array(generated.questions.length).fill(null));
          setGeneratedBy(generated.generatedBy || '');
          return;
        }
      }
      const content = text || SAMPLE_TEXT;
      const generated = await apiGenerateQuiz(content, questionCount, difficulty);
      setQuestions(generated.questions);
      setAnswers(new Array(generated.questions.length).fill(null));
      setGeneratedBy(generated.generatedBy || '');
    } finally {
      setGenerating(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const ext = (file.name.split('.').pop() || '').toLowerCase();
    setUploadedFile(file);
    setFileName(file.name);
    const textual = ['txt', 'srt', 'vtt'].includes(ext);
    if (textual) {
      const reader = new FileReader();
      reader.onload = (ev) => {
        setText(ev.target?.result as string || SAMPLE_TEXT);
      };
      reader.readAsText(file);
    } else {
      setText('');
    }
    e.target.value = '';
  };

  const startQuiz = () => setInQuiz(true);

  const handleAnswer = (qi: number, oi: number) => {
    if (submitted) return;
    const newAnswers = [...answers];
    newAnswers[qi] = oi;
    setAnswers(newAnswers);
  };

  const handleSubmit = async () => {
    setSubmitted(true);
    await saveQuiz(
      `${difficulty} Quiz - ${new Date().toLocaleDateString()}`,
      questions,
      answers,
    );
  };

  const handleDelete = (id: string) => {
    setQuestions(prev => prev.filter(q => q.id !== id));
  };

  const handleRegenerate = async (id: string) => {
    const generated = await apiGenerateQuiz(text || SAMPLE_TEXT, 1, difficulty);
    const newQ = generated.questions[0];
    setQuestions(prev => prev.map(q => q.id === id ? { ...newQ, id } : q));
  };

  const handleSaveEdit = (id: string) => {
    setQuestions(prev => prev.map(q => q.id === id ? { ...q, question: editText } : q));
    setEditingId(null);
  };

  const score = submitted ? questions.reduce((acc, q, i) => acc + (answers[i] === q.correctAnswer ? 1 : 0), 0) : 0;

  if (inQuiz) {
    return (
      <div>
        <Header title="Quiz in Progress" />
        <div className="p-6 max-w-3xl mx-auto space-y-6">
          {submitted && (
            <Card className="bg-gradient-to-r from-navy-800 to-navy-900 text-white">
              <div className="text-center py-4">
                <h2 className="text-2xl font-bold mb-1">Quiz Complete!</h2>
                <p className="text-4xl font-bold text-saffron-400">{score}/{questions.length}</p>
                <p className="text-navy-200 mt-1">{Math.round(score / questions.length * 100)}% Score</p>
                <div className="flex gap-3 justify-center mt-4">
                  <Button onClick={() => { setInQuiz(false); setSubmitted(false); setQuestions([]); }} variant="ghost" className="text-white border border-white/20">New Quiz</Button>
                  <Button onClick={() => { setSubmitted(false); setAnswers(new Array(questions.length).fill(null)); }}>Retake Quiz</Button>
                </div>
              </div>
            </Card>
          )}

          {!submitted && (
            <div className="flex items-center justify-between stagger-fade-up" style={staggerStyle(0, animate)}>
              <p className="text-sm text-navy-500">Answer all questions, then submit</p>
              <Button onClick={handleSubmit}>Submit Quiz</Button>
            </div>
          )}

          {questions.map((q, qi) => (
            <Card key={q.id} className="stagger-fade-up" style={staggerStyle(1 + qi, animate)}>
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="w-7 h-7 rounded-full bg-navy-100 flex items-center justify-center text-xs font-bold text-navy-600">{qi + 1}</span>
                  <Badge variant={q.difficulty === 'Easy' ? 'success' : q.difficulty === 'Medium' ? 'warning' : 'danger'}>{q.difficulty}</Badge>
                </div>
              </div>
              <p className="text-sm font-medium text-navy-800 mb-3">{q.question}</p>
              <div className="space-y-2">
                {q.options.map((opt, oi) => {
                  let optStyle = 'border-navy-200 hover:border-navy-300 bg-white';
                  if (submitted) {
                    if (oi === q.correctAnswer) optStyle = 'border-green-400 bg-green-50';
                    else if (answers[qi] === oi) optStyle = 'border-red-400 bg-red-50';
                  } else if (answers[qi] === oi) {
                    optStyle = 'border-saffron-400 bg-saffron-50';
                  }
                  return (
                    <button
                      key={oi}
                      onClick={() => handleAnswer(qi, oi)}
                      className={`w-full text-left p-3 rounded-lg border text-sm transition-all cursor-pointer ${optStyle}`}
                    >
                      <span className="font-medium text-navy-500 mr-2">{String.fromCharCode(65 + oi)}.</span>
                      {opt}
                      {submitted && oi === q.correctAnswer && <Check size={14} className="inline ml-2 text-green-500" />}
                      {submitted && answers[qi] === oi && oi !== q.correctAnswer && <X size={14} className="inline ml-2 text-red-500" />}
                    </button>
                  );
                })}
              </div>
              {submitted && (
                <div className={`mt-3 p-3 rounded-lg text-xs ${answers[qi] === q.correctAnswer ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                  <p className="font-medium mb-1">{answers[qi] === q.correctAnswer ? 'Correct!' : 'Incorrect'}</p>
                  <p>{q.explanation}</p>
                </div>
              )}
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <Header title="AI Quiz Generator" />
      <div className="p-6 space-y-6 max-w-4xl mx-auto">
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 flex items-start gap-2 stagger-fade-up" style={staggerStyle(0, animate)}>
          <AlertTriangle size={16} className="text-amber-500 mt-0.5 shrink-0" />
          <p className="text-xs text-amber-700">AI-generated questions should be reviewed by an authorized trainer before official use.</p>
        </div>

        <Card className="stagger-fade-up" style={staggerStyle(1, animate)}>
          <h2 className="text-base font-semibold text-navy-800 mb-4">Input Learning Material</h2>

          <div className="flex gap-3 mb-4">
            <Button variant={inputMethod === 'paste' ? 'primary' : 'ghost'} size="sm" onClick={() => setInputMethod('paste')}>
              <FileText size={14} className="mr-1" /> Paste Text
            </Button>
            <Button variant={inputMethod === 'upload' ? 'primary' : 'ghost'} size="sm" onClick={() => setInputMethod('upload')}>
              <Upload size={14} className="mr-1" /> Upload File
            </Button>
          </div>

          {inputMethod === 'paste' ? (
            <textarea
              value={text}
              onChange={e => setText(e.target.value)}
              placeholder="Paste your learning content here... (Leave empty to use sample content)"
              className="w-full h-40 p-3 border border-navy-200 rounded-lg text-sm resize-none focus:ring-2 focus:ring-saffron-400 outline-none"
            />
          ) : (
            <div className="border-2 border-dashed border-navy-200 rounded-lg p-8 text-center">
              <input ref={fileInputRef} type="file" accept=".pdf,.docx,.pptx,.ppt,.txt,.srt,.vtt" onChange={handleFileUpload} className="hidden" />
              <Upload size={32} className="mx-auto text-navy-300 mb-2" />
              <p className="text-sm text-navy-500 mb-2">Drag & drop or click to upload</p>
              <p className="text-xs text-navy-400 mb-3">PDF, DOCX, PPTX, TXT, SRT, VTT transcripts</p>
              <Button size="sm" onClick={() => fileInputRef.current?.click()}>Choose File</Button>
              {fileName ? (
                <p className="text-xs text-green-600 mt-2 font-medium">📄 {fileName} — loaded for real text extraction</p>
              ) : (
                <p className="text-xs text-navy-400 mt-2">Supported formats are parsed server-side; SRT/VTT timestamps are stripped automatically.</p>
              )}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
            <div>
              <label className="block text-sm font-medium text-navy-700 mb-1">Number of Questions</label>
              <select value={questionCount} onChange={e => setQuestionCount(Number(e.target.value))} className="w-full px-3 py-2 border border-navy-200 rounded-lg text-sm bg-white">
                <option value={5}>5 Questions</option>
                <option value={10}>10 Questions</option>
                <option value={15}>15 Questions</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-navy-700 mb-1">Difficulty</label>
              <select value={difficulty} onChange={e => setDifficulty(e.target.value)} className="w-full px-3 py-2 border border-navy-200 rounded-lg text-sm bg-white">
                <option value="Easy">Easy</option>
                <option value="Medium">Medium</option>
                <option value="Hard">Hard</option>
              </select>
            </div>
            <div className="flex items-end">
              <Button onClick={handleGenerate} disabled={generating} className="w-full">
                {generating ? (
                  <><span className="animate-spin mr-2">⟳</span> Generating...</>
                ) : (
                  <><Brain size={16} className="mr-1" /> Generate Quiz</>
                )}
              </Button>
            </div>
          </div>
        </Card>

        {questions.length > 0 && !inQuiz && (
          <>
            <div className="flex items-center justify-between stagger-fade-up" style={staggerStyle(2, animate)}>
              <h2 className="text-base font-semibold text-navy-800">Generated Questions ({questions.length})</h2>
              <div className="flex items-center gap-2">
                {generatedBy && (
                  <Badge variant={generatedBy.startsWith('llm') ? 'success' : 'default'}>
                    {generatedBy.startsWith('llm') ? `AI · ${generatedBy.split(':')[1] ?? ''}` : 'Rule-based'}
                  </Badge>
                )}
                <Button onClick={startQuiz}>Start Quiz</Button>
              </div>
            </div>

            {questions.map((q, qi) => (
              <Card key={q.id} className="stagger-fade-up" style={staggerStyle(3 + qi, animate)}>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="w-6 h-6 rounded-full bg-navy-100 flex items-center justify-center text-xs font-bold text-navy-600">{qi + 1}</span>
                      <Badge variant={q.difficulty === 'Easy' ? 'success' : q.difficulty === 'Medium' ? 'warning' : 'danger'}>{q.difficulty}</Badge>
                    </div>
                    {editingId === q.id ? (
                      <div className="flex gap-2 mb-2">
                        <input value={editText} onChange={e => setEditText(e.target.value)} className="flex-1 px-3 py-1 border border-navy-200 rounded text-sm" />
                        <Button size="sm" onClick={() => handleSaveEdit(q.id)}>Save</Button>
                        <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}>Cancel</Button>
                      </div>
                    ) : (
                      <p className="text-sm font-medium text-navy-800 mb-2">{q.question}</p>
                    )}
                    <div className="grid grid-cols-2 gap-2">
                      {q.options.map((opt, oi) => (
                        <div key={oi} className={`p-2 rounded text-xs ${oi === q.correctAnswer ? 'bg-green-50 border border-green-200' : 'bg-navy-50 border border-navy-100'}`}>
                          <span className="font-medium text-navy-500 mr-1">{String.fromCharCode(65 + oi)}.</span> {opt}
                        </div>
                      ))}
                    </div>
                    <p className="text-xs text-navy-400 mt-2 italic">Source: {q.sourceExcerpt}</p>
                  </div>
                  <div className="flex gap-1 ml-3">
                    <button onClick={() => { setEditingId(q.id); setEditText(q.question); }} className="p-1.5 rounded hover:bg-navy-100 cursor-pointer"><Edit3 size={14} className="text-navy-400" /></button>
                    <button onClick={() => handleRegenerate(q.id)} className="p-1.5 rounded hover:bg-navy-100 cursor-pointer"><RotateCcw size={14} className="text-navy-400" /></button>
                    <button onClick={() => handleDelete(q.id)} className="p-1.5 rounded hover:bg-red-100 cursor-pointer"><Trash2 size={14} className="text-red-400" /></button>
                  </div>
                </div>
              </Card>
            ))}
          </>
        )}
      </div>
    </div>
  );
}

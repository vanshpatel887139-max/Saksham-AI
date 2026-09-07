import Header from '../components/layout/Header';
import { Card, Badge } from '../components/ui/UIComponents';
import { useApp } from '../store/AppContext';
import { BookOpen, CheckCircle } from 'lucide-react';
import { useStagger } from '../hooks/useStagger';

export default function AssessmentsPage() {
  const { quizzes } = useApp();
  const { animate, staggerStyle } = useStagger();

  return (
    <div>
      <Header title="My Assessments" />
      <div className="p-6 space-y-6">
        {quizzes.length === 0 ? (
          <Card className="stagger-fade-up" style={staggerStyle(0, animate)}>
            <div className="text-center py-12">
              <BookOpen size={40} className="mx-auto text-navy-200 mb-3" />
              <h3 className="text-lg font-semibold text-navy-700 mb-1">No Assessments Yet</h3>
              <p className="text-sm text-navy-400">Take a quiz from the AI Quiz Generator to see your results here.</p>
            </div>
          </Card>
        ) : (
          <div className="space-y-4">
            {quizzes.map((quiz, i) => (
              <Card key={quiz.id} className="stagger-fade-up" style={staggerStyle(1 + i, animate)}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${quiz.score !== undefined && quiz.score / quiz.totalQuestions >= 0.7 ? 'bg-green-100' : 'bg-amber-100'}`}>
                      <CheckCircle size={24} className={quiz.score !== undefined && quiz.score / quiz.totalQuestions >= 0.7 ? 'text-green-600' : 'text-amber-600'} />
                    </div>
                    <div>
                      <h3 className="font-semibold text-navy-800">{quiz.title}</h3>
                      <p className="text-xs text-navy-400">{quiz.totalQuestions} questions • {quiz.date}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-navy-800">{quiz.score}/{quiz.totalQuestions}</p>
                    <Badge variant={quiz.score !== undefined && quiz.score / quiz.totalQuestions >= 0.7 ? 'success' : 'warning'}>
                      {quiz.score !== undefined && quiz.score / quiz.totalQuestions >= 0.7 ? 'Passed' : 'Needs Improvement'}
                    </Badge>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

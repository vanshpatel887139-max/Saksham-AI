import Header from '../components/layout/Header';
import { Card, Badge } from '../components/ui/UIComponents';
import { useApp, useI18n } from '../store/AppContext';
import { BookOpen, CheckCircle } from 'lucide-react';
import { useStagger } from '../hooks/useStagger';

export default function AssessmentsPage() {
  const { quizzes } = useApp();
  const { t } = useI18n();
  const { animate, staggerStyle } = useStagger();

  return (
    <div>
      <Header title={t('My Assessments', 'मेरे आकलन')} />
      <div className="p-6 space-y-6">
        {quizzes.length === 0 ? (
          <Card className="stagger-fade-up" style={staggerStyle(0, animate)}>
            <div className="text-center py-12">
              <BookOpen size={40} className="mx-auto text-navy-200 mb-3" />
              <h3 className="text-lg font-semibold text-navy-700 mb-1">{t('No Assessments Yet', 'अभी कोई आकलन नहीं')}</h3>
              <p className="text-sm text-navy-400">
                {t('Take a quiz from the AI Quiz Generator to see your results here.', 'अपने परिणाम यहाँ देखने के लिए एआई क्विज़ जनरेटर से एक क्विज़ दें।')}
              </p>
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
                      <p className="text-xs text-navy-400">
                        {quiz.totalQuestions} {t('questions', 'प्रश्न')} • {quiz.date}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-navy-800">{quiz.score}/{quiz.totalQuestions}</p>
                    <Badge variant={quiz.score !== undefined && quiz.score / quiz.totalQuestions >= 0.7 ? 'success' : 'warning'}>
                      {quiz.score !== undefined && quiz.score / quiz.totalQuestions >= 0.7
                        ? t('Passed', 'उत्तीर्ण')
                        : t('Needs Improvement', 'सुधार की आवश्यकता')}
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

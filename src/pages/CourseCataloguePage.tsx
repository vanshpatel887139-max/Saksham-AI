import Header from '../components/layout/Header';
import { Card, Button, Badge, ProgressBar, BadgeVariant } from '../components/ui/UIComponents';
import { useApp } from '../store/AppContext';
import { courses } from '../data/mockData';
import { BookOpen, Star, Clock, Award, Filter, Search } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStagger } from '../hooks/useStagger';

const difficultyColors: Record<string, BadgeVariant> = {
  'Beginner': 'success',
  'Intermediate': 'warning',
  'Advanced': 'danger',
};

export default function CourseCataloguePage() {
  const { skillGaps, enrollInCourse, enrolledCourses } = useApp();
  const navigate = useNavigate();
  const { animate, staggerStyle } = useStagger();
  const [filterProvider, setFilterProvider] = useState('all');
  const [filterDifficulty, setFilterDifficulty] = useState('all');
  const [search, setSearch] = useState('');

  const filtered = courses.filter(c => {
    if (filterProvider !== 'all' && c.provider !== filterProvider) return false;
    if (filterDifficulty !== 'all' && c.difficulty !== filterDifficulty) return false;
    if (search && !c.title.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const getRecommendationReason = (course: typeof courses[0]) => {
    const gaps = skillGaps.filter(g => course.skillsCovered.includes(g.competencyName));
    if (gaps.length === 0) return null;
    const mainGap = gaps.sort((a, b) => b.gap - a.gap)[0];
    return `Recommended because your ${mainGap.competencyName} is Level ${mainGap.currentLevel}, while Level ${mainGap.requiredLevel} is required for your target role.`;
  };

  const isEnrolled = (id: string) => enrolledCourses.some(c => c.id === id);

  return (
    <div>
      <Header title="Course Catalogue" />
      <div className="p-6 space-y-6">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 stagger-fade-up" style={staggerStyle(0, animate)}>
          <div className="flex items-center gap-2">
            <span className="px-2 py-1 bg-blue-100 text-blue-700 text-[10px] font-bold rounded">MOCK iGOT API INTEGRATION</span>
            <span className="px-2 py-1 bg-green-100 text-green-700 text-[10px] font-bold rounded">NSSTA TPAC</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-navy-400" />
              <input
                type="text"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search courses..."
                className="pl-9 pr-3 py-2 border border-navy-200 rounded-lg text-sm w-48"
              />
            </div>
            <select value={filterProvider} onChange={e => setFilterProvider(e.target.value)} className="px-3 py-2 border border-navy-200 rounded-lg text-sm bg-white">
              <option value="all">All Providers</option>
              <option value="iGOT Karmayogi">iGOT Karmayogi</option>
              <option value="NSSTA">NSSTA</option>
            </select>
            <select value={filterDifficulty} onChange={e => setFilterDifficulty(e.target.value)} className="px-3 py-2 border border-navy-200 rounded-lg text-sm bg-white">
              <option value="all">All Levels</option>
              <option value="Beginner">Beginner</option>
              <option value="Intermediate">Intermediate</option>
              <option value="Advanced">Advanced</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map((course, i) => {
            const reason = getRecommendationReason(course);
            const enrolled = isEnrolled(course.id);
            const enrollment = enrolledCourses.find(c => c.id === course.id);

            return (
              <Card key={course.id} padding={false} className="overflow-hidden stagger-fade-up" style={staggerStyle(1 + i, animate)}>
                <div className="h-32 bg-gradient-to-br from-navy-700 to-navy-900 flex items-center justify-center">
                  <span className="text-4xl">{course.thumbnail}</span>
                </div>
                <div className="p-5">
                  <div className="flex items-center gap-2 mb-2">
                    <Badge variant={course.provider === 'iGOT Karmayogi' ? 'info' : 'success'}>{course.provider}</Badge>
                    <Badge variant={difficultyColors[course.difficulty]}>{course.difficulty}</Badge>
                  </div>
                  <h3 className="font-semibold text-navy-800 mb-1">{course.title}</h3>
                  <p className="text-xs text-navy-400 mb-3 line-clamp-2">{course.description}</p>

                  <div className="flex items-center gap-3 text-xs text-navy-400 mb-3">
                    <span className="flex items-center gap-1"><Clock size={12} /> {course.duration}</span>
                    <span className="flex items-center gap-1"><Star size={12} className="text-amber-400" /> {course.rating}</span>
                    <span>{course.language}</span>
                  </div>

                  <div className="flex flex-wrap gap-1 mb-3">
                    {course.skillsCovered.map(s => (
                      <span key={s} className="px-2 py-0.5 bg-navy-50 text-navy-600 rounded text-[10px]">{s}</span>
                    ))}
                  </div>

                  {reason && (
                    <div className="bg-saffron-50 border border-saffron-200 rounded-lg px-3 py-2 mb-3">
                      <p className="text-[11px] text-saffron-700 flex items-start gap-1">
                        <Award size={12} className="mt-0.5 shrink-0" />
                        {reason}
                      </p>
                    </div>
                  )}

                  {enrolled && enrollment ? (
                    <button onClick={() => navigate(`/courses/${course.id}`)} className="w-full text-left cursor-pointer">
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-navy-500">Progress</span>
                        <span className="font-medium text-navy-700">{enrollment.progress}%</span>
                      </div>
                      <ProgressBar value={enrollment.progress} max={100} size="sm" showLabel={false} />
                    </button>
                  ) : (
                    <div className="flex gap-2">
                      <Button size="sm" className="flex-1" onClick={() => navigate(`/courses/${course.id}`)}>
                        <BookOpen size={14} className="mr-1" /> View Course
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => enrollInCourse(course.id)}>
                        Enroll
                      </Button>
                    </div>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}

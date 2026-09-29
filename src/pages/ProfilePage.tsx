import { useState } from 'react';
import Header from '../components/layout/Header';
import { Card, Button, Input, Select } from '../components/ui/UIComponents';
import { useApp, useI18n } from '../store/AppContext';
import { Save, Edit } from 'lucide-react';

const departments = ['National Sample Survey Office', 'Census Division', 'DGCIS', 'NSSTA', 'Other'];
const departmentLabels: Record<string, string> = {
  'National Sample Survey Office': 'राष्ट्रीय प्रतिदर्श सर्वेक्षण कार्यालय',
  'Census Division': 'जनगणना प्रभाग',
  'DGCIS': 'डीजीसीआईएस',
  'NSSTA': 'एनएसएसटीए',
  'Other': 'अन्य',
};
const languages = ['English', 'Hindi', 'Bengali', 'Tamil', 'Telugu', 'Marathi'];
const languageLabels: Record<string, string> = {
  'English': 'अंग्रेज़ी',
  'Hindi': 'हिन्दी',
  'Bengali': 'बंगाली',
  'Tamil': 'तमिल',
  'Telugu': 'तेलुगु',
  'Marathi': 'मराठी',
};

export default function ProfilePage() {
  const { user, updateUserProfile } = useApp();
  const { t } = useI18n();
  const [editing, setEditing] = useState(!user?.profileCompleted);
  const [form, setForm] = useState({
    name: user?.name || '',
    employeeId: user?.employeeId || '',
    designation: user?.designation || '',
    department: user?.department || '',
    currentRole: user?.currentRole || '',
    education: user?.education || '',
    experience: user?.experience || 0,
    careerGoal: user?.careerGoal || '',
    previousTraining: user?.previousTraining || '',
    preferredLanguage: user?.preferredLanguage || 'English',
  });

  const update = (field: string, value: string | number) => {
    setForm(prev => ({ ...prev, [field]: value }));
  };

  const handleSave = () => {
    updateUserProfile({ ...form, profileCompleted: true });
    setEditing(false);
  };

  if (!user) return null;

  const completionPct = Math.round(
    (Object.values(form).filter(v => v !== '' && v !== 0).length / Object.keys(form).length) * 100
  );

  return (
    <div>
      <Header title={t('My Profile', 'मेरी प्रोफ़ाइल')} />
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-navy-400">{t('Complete your profile for personalized recommendations', 'व्यक्तिगत अनुशंसाओं हेतु अपनी प्रोफ़ाइल पूरी करें')}</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-navy-600">{t('Profile', 'प्रोफ़ाइल')} {completionPct}% {t('complete', 'पूर्ण')}</span>
            <div className="w-24 h-2 bg-navy-100 rounded-full">
              <div className="h-2 bg-saffron-500 rounded-full transition-all" style={{ width: `${completionPct}%` }} />
            </div>
          </div>
        </div>

        <Card>
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-navy-800">{t('Personal Information', 'व्यक्तिगत जानकारी')}</h2>
            <Button variant={editing ? 'primary' : 'ghost'} onClick={() => editing ? handleSave() : setEditing(true)}>
              {editing ? <><Save size={16} className="mr-1" /> {t('Save Changes', 'परिवर्तन सहेजें')}</> : <><Edit size={16} className="mr-1" /> {t('Edit Profile', 'प्रोफ़ाइल संपादित करें')}</>}
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input label={t('Full Name', 'पूरा नाम')} value={form.name} onChange={v => update('name', v)} disabled={!editing} />
            <Input label={t('Employee ID', 'कर्मचारी आईडी')} value={form.employeeId} onChange={v => update('employeeId', v)} disabled={!editing} />
            <Input label={t('Designation', 'पदनाम')} value={form.designation} onChange={v => update('designation', v)} disabled={!editing} />
            <Select label={t('Department', 'विभाग')} value={form.department} onChange={v => update('department', v)} options={departments.map(d => ({ value: d, label: t(d, departmentLabels[d] || d) }))} />
            <Input label={t('Current Job Role', 'वर्तमान पद')} value={form.currentRole} onChange={v => update('currentRole', v)} disabled={!editing} />
            <Input label={t('Educational Qualification', 'शैक्षिक योग्यता')} value={form.education} onChange={v => update('education', v)} disabled={!editing} />
            <Input label={t('Years of Experience', 'अनुभव वर्ष')} value={String(form.experience)} onChange={v => update('experience', parseInt(v) || 0)} type="number" disabled={!editing} />
            <Select label={t('Preferred Learning Language', 'पसंदीदा अध्ययन भाषा')} value={form.preferredLanguage} onChange={v => update('preferredLanguage', v)} options={languages.map(l => ({ value: l, label: t(l, languageLabels[l] || l) }))} />
          </div>

          <div className="mt-4">
            <Input label={t('Career Goal', 'वर्तमान करियर लक्ष्य')} value={form.careerGoal} onChange={v => update('careerGoal', v)} disabled={!editing} />
          </div>
          <div className="mt-4">
            <Input label={t('Previous Training', 'पूर्व प्रशिक्षण')} value={form.previousTraining} onChange={v => update('previousTraining', v)} disabled={!editing} />
          </div>
        </Card>

        <Card>
          <h2 className="text-lg font-semibold text-navy-800 mb-4">{t('Account Details', 'खाता विवरण')}</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-navy-50 rounded-lg">
              <p className="text-xs text-navy-400 mb-1">{t('Role', 'भूमिका')}</p>
              <p className="text-sm font-medium text-navy-800 capitalize">{user.role}</p>
            </div>
            <div className="p-4 bg-navy-50 rounded-lg">
              <p className="text-xs text-navy-400 mb-1">{t('Account Status', 'खाता स्थिति')}</p>
              <p className="text-sm font-medium text-green-600">{t('Active', 'सक्रिय')}</p>
            </div>
            <div className="p-4 bg-navy-50 rounded-lg">
              <p className="text-xs text-navy-400 mb-1">{t('SSO Integration', 'एसएसओ एकीकरण')}</p>
              <p className="text-sm font-medium text-navy-600">{t('Demo Mode', 'डेमो मोड')}</p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

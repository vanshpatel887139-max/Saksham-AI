import { useState } from 'react';
import Header from '../components/layout/Header';
import { Card, Button, Input, Select } from '../components/ui/UIComponents';
import { useApp } from '../store/AppContext';
import { Save, Edit } from 'lucide-react';

const departments = ['National Sample Survey Office', 'Census Division', 'DGCIS', 'NSSTA', 'Other'];
const languages = ['English', 'Hindi', 'Bengali', 'Tamil', 'Telugu', 'Marathi'];

export default function ProfilePage() {
  const { user, updateUserProfile } = useApp();
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
      <Header title="My Profile" />
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-navy-400">Complete your profile for personalized recommendations</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-navy-600">Profile {completionPct}% complete</span>
            <div className="w-24 h-2 bg-navy-100 rounded-full">
              <div className="h-2 bg-saffron-500 rounded-full transition-all" style={{ width: `${completionPct}%` }} />
            </div>
          </div>
        </div>

        <Card>
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-navy-800">Personal Information</h2>
            <Button variant={editing ? 'primary' : 'ghost'} onClick={() => editing ? handleSave() : setEditing(true)}>
              {editing ? <><Save size={16} className="mr-1" /> Save Changes</> : <><Edit size={16} className="mr-1" /> Edit Profile</>}
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input label="Full Name" value={form.name} onChange={v => update('name', v)} disabled={!editing} />
            <Input label="Employee ID" value={form.employeeId} onChange={v => update('employeeId', v)} disabled={!editing} />
            <Input label="Designation" value={form.designation} onChange={v => update('designation', v)} disabled={!editing} />
            <Select label="Department" value={form.department} onChange={v => update('department', v)} options={departments.map(d => ({ value: d, label: d }))} />
            <Input label="Current Job Role" value={form.currentRole} onChange={v => update('currentRole', v)} disabled={!editing} />
            <Input label="Educational Qualification" value={form.education} onChange={v => update('education', v)} disabled={!editing} />
            <Input label="Years of Experience" value={String(form.experience)} onChange={v => update('experience', parseInt(v) || 0)} type="number" disabled={!editing} />
            <Select label="Preferred Learning Language" value={form.preferredLanguage} onChange={v => update('preferredLanguage', v)} options={languages.map(l => ({ value: l, label: l }))} />
          </div>

          <div className="mt-4">
            <Input label="Career Goal" value={form.careerGoal} onChange={v => update('careerGoal', v)} disabled={!editing} />
          </div>
          <div className="mt-4">
            <Input label="Previous Training" value={form.previousTraining} onChange={v => update('previousTraining', v)} disabled={!editing} />
          </div>
        </Card>

        <Card>
          <h2 className="text-lg font-semibold text-navy-800 mb-4">Account Details</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-navy-50 rounded-lg">
              <p className="text-xs text-navy-400 mb-1">Role</p>
              <p className="text-sm font-medium text-navy-800 capitalize">{user.role}</p>
            </div>
            <div className="p-4 bg-navy-50 rounded-lg">
              <p className="text-xs text-navy-400 mb-1">Account Status</p>
              <p className="text-sm font-medium text-green-600">Active</p>
            </div>
            <div className="p-4 bg-navy-50 rounded-lg">
              <p className="text-xs text-navy-400 mb-1">SSO Integration</p>
              <p className="text-sm font-medium text-navy-600">Demo Mode</p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

import { useState } from 'react';
import { updateConnection, type DBConnectionItem } from '../api/client';
import LoadingDots from './LoadingDots';

interface Props {
  conn: DBConnectionItem;
  onClose: () => void;
  onSaved: (updated: DBConnectionItem) => void;
}

export default function EditConnectionModal({ conn, onClose, onSaved }: Props) {
  const [form, setForm] = useState({
    connection_name: conn.connection_name,
    host:            conn.host,
    port:            conn.port,
    database_name:   conn.database_name,
    username:        conn.username,
    password:        '',
    ssl_enabled:     conn.ssl_enabled,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState('');

  const set = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = field === 'port' ? Number(e.target.value)
              : field === 'ssl_enabled' ? e.target.checked
              : e.target.value;
    setForm(f => ({ ...f, [field]: val }));
  };

  const handleSave = async () => {
    setSaving(true); setError('');
    try {
      const payload: any = { ...form };
      if (!payload.password) delete payload.password; // don't send empty password
      const updated = await updateConnection(conn.id, payload);
      onSaved(updated);
    } catch (e: any) {
      setError(e.message || 'Failed to update connection');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="db-modal-overlay" onClick={onClose}>
      <div className="db-modal" onClick={e => e.stopPropagation()}>
        <div className="db-modal-header">
          <h3>Edit Connection</h3>
          <button className="db-modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="db-modal-body">
          <div className="form-grid">
            {[
              { label: 'Connection Name', field: 'connection_name', type: 'text' },
              { label: 'Host',            field: 'host',            type: 'text' },
              { label: 'Port',            field: 'port',            type: 'number' },
              { label: 'Database Name',   field: 'database_name',   type: 'text' },
              { label: 'Username',        field: 'username',        type: 'text' },
              { label: 'Password (leave blank to keep)',  field: 'password', type: 'password' },
            ].map(({ label, field, type }) => (
              <div className="field-group" key={field}>
                <label>{label}</label>
                <input type={type} value={(form as any)[field]}
                       onChange={set(field)} placeholder={label} />
              </div>
            ))}
            <div className="field-group field-checkbox">
              <label>
                <input type="checkbox" checked={form.ssl_enabled} onChange={set('ssl_enabled')} />
                Enable SSL
              </label>
            </div>
          </div>
          {error && <div className="error-banner" style={{ marginTop: '12px' }}>{error}</div>}
        </div>
        <div className="db-modal-footer">
          <button className="btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? <LoadingDots /> : 'Save & Validate'}
          </button>
        </div>
      </div>
    </div>
  );
}

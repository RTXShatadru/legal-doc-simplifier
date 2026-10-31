export const workspaces = [
  { id: 'property', name: 'Property & agreements', short: 'Property', icon: 'file', color: '#63774b', description: 'Sale deeds, rentals and the fine print.', label: 'Deeds · Rentals · Agreements' },
  { id: 'finance', name: 'Finance', short: 'Finance', icon: 'shield', color: '#a87537', description: 'Understand borrowing costs and commitments.', label: 'Loans · Cards · Insurance' },
  { id: 'hr', name: 'Career & employment', short: 'Career', icon: 'grid', color: '#78649c', description: 'Explore your skills and employment terms.', label: 'Resumes · Job matches · Offers' },
  { id: 'medical', name: 'Medical', short: 'Medical', icon: 'book', color: '#40838a', description: 'Make sense of reports and health paperwork.', label: 'Reports · Prescriptions · Policies' },
  { id: 'court', name: 'Court & legal notices', short: 'Court', icon: 'clock', color: '#9a6453', description: 'Find required actions and stated deadlines.', label: 'Notices · Summons · Orders' },
];
export const workspaceFor = id => workspaces.find(w => w.id === id) || workspaces[0];
export const allowedFiles = domain => domain === 'hr' ? '.pdf,.docx' : domain === 'medical' ? '.pdf,.jpg,.jpeg,.png,.webp' : '.pdf';

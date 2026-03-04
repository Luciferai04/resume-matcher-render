'use client';

import { useState, useEffect } from 'react';
import { getUserId, setUserId } from '@/lib/api/auth';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import Users from 'lucide-react/dist/esm/icons/users';
import Check from 'lucide-react/dist/esm/icons/check';

const MOCK_USERS = [
    { id: 'student_001', name: 'Student 1 (Day 1 Role)' },
    { id: 'student_002', name: 'Student 2 (Tech Lead)' },
    { id: 'student_003', name: 'Student 3 (Product Manager)' },
    { id: 'admin_demo', name: 'Admin/Instructor View' },
];

export function UserSwitcher() {
    const [currentId, setCurrentId] = useState<string>('');
    const [isOpen, setIsOpen] = useState(false);

    useEffect(() => {
        setCurrentId(getUserId());
    }, []);

    const handleSwitch = (id: string) => {
        if (id === currentId) return;
        setUserId(id);
    };

    return (
        <div className="fixed bottom-6 right-6 z-50">
            {isOpen && (
                <Card className="mb-4 p-4 shadow-sw-lg border-2 border-black bg-white w-64 animate-in fade-in slide-in-from-bottom-2">
                    <h3 className="font-mono text-xs font-bold uppercase mb-3 text-gray-500 tracking-widest">
                        Switch Context
                    </h3>
                    <div className="space-y-2">
                        {MOCK_USERS.map((user) => (
                            <button
                                key={user.id}
                                onClick={() => handleSwitch(user.id)}
                                className={`w-full text-left px-3 py-2 text-sm font-mono uppercase transition-colors flex items-center justify-between ${currentId === user.id
                                        ? 'bg-primary text-canvas font-bold'
                                        : 'hover:bg-gray-100'
                                    }`}
                            >
                                <span>{user.name}</span>
                                {currentId === user.id && <Check className="w-4 h-4" />}
                            </button>
                        ))}
                    </div>
                    <p className="mt-4 text-[10px] font-mono text-gray-400 leading-tight">
                        MVP: Toggling student identities via X-User-ID header.
                    </p>
                </Card>
            )}
            <Button
                onClick={() => setIsOpen(!isOpen)}
                className="w-14 h-14 rounded-none bg-black text-white shadow-sw-default hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-none transition-all border-2 border-black"
            >
                <Users className="w-6 h-6" />
            </Button>
        </div>
    );
}

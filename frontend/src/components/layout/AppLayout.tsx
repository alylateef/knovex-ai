import React from 'react';
import { Shelf } from '../shelf/Shelf.tsx';
import { TopBar } from '../desk/TopBar.tsx';
import { ThreadDesk } from '../desk/ThreadDesk.tsx';
import { Inspector } from '../source/Inspector.tsx';

export const AppLayout: React.FC = () => {
  return (
    <div className="w-full h-full flex flex-col md:flex-row overflow-hidden bg-bg text-ink">
      {/* Left Shelf 250px */}
      <Shelf />

      {/* Center Desk */}
      <div className="flex-1 flex flex-col h-full overflow-hidden min-w-0">
        <TopBar />
        <ThreadDesk />
      </div>

      {/* Right Source Inspector 370px (or bottom sheet on mobile) */}
      <Inspector />
    </div>
  );
};

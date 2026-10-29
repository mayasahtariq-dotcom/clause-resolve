/** Fixed, slowly drifting colour blobs behind every page: depth without noise. */
export function Backdrop() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="bg-dots absolute inset-0 opacity-60" />
      <div className="absolute -left-32 -top-24 h-[28rem] w-[28rem] animate-drift rounded-full bg-sun/40 blur-3xl" />
      <div className="absolute -right-24 top-40 h-[26rem] w-[26rem] animate-drift-slow rounded-full bg-bubblegum/25 blur-3xl" />
      <div className="absolute bottom-[-8rem] left-1/3 h-[24rem] w-[24rem] animate-drift rounded-full bg-lagoon/25 blur-3xl [animation-delay:-6s]" />
      <div className="absolute right-1/4 top-[55%] h-[18rem] w-[18rem] animate-drift-slow rounded-full bg-iris/20 blur-3xl" />
    </div>
  );
}

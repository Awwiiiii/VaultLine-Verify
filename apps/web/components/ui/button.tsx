import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
const styles = cva("inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-50", { variants: { variant: { default: "bg-blue-700 text-white hover:bg-blue-800", outline: "border border-slate-200 bg-white hover:bg-slate-50" } }, defaultVariants: { variant: "default" } });
export function Button({ asChild = false, variant, className, ...props }: React.ComponentProps<"button"> & VariantProps<typeof styles> & { asChild?: boolean }) { const Component = asChild ? Slot : "button"; return <Component className={cn(styles({ variant }), className)} {...props} />; }

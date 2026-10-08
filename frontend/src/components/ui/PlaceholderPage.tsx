import { Construction } from "lucide-react";
import Card from "./Card";

interface PlaceholderPageProps {
    title: string;
}

export function PlaceholderPage({ title }: PlaceholderPageProps) {
    return (
        <div>
            <h1 className="font-heading text-2xl text-espresso md:text-3xl">{title}</h1>
            <Card className="mt-4 flex flex-col items-center gap-3 py-12 text-center">
                <Construction className="h-10 w-10 text-saffron" aria-hidden="true" />
                <p className="text-espresso/70">{title} page coming soon.</p>
            </Card>
        </div>
    );
}
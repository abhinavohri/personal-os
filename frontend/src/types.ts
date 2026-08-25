export type Lesson={slug:string,title:string,summary:string,minutes:number,status:'locked'|'available'|'completed'|'mastered',playable:boolean,bestScore:number};
export type Unit={slug:string,title:string,description:string,icon:string,number:number,lessons:Lesson[],completed:number,total:number};
export type Course={learner:{id:string,name:string,xp:number,streak:number,dailyGoal:number},units:Unit[],nextLesson:string|null,stats?:{completed:number,accuracy:number,attempts:number,review:number}};
export type Card={id:string,type:'story'|'choice'|'order'|'number',title?:string,body?:string,label?:string,accent?:string,bullets?:string[],ladder?:string[][],prompt?:string,options?:string[],items?:string[],suffix?:string};
export type Session={id:string,lesson:{slug:string,eyebrow:string,title:string,description:string},position:number,total:number,hearts:number,xpEarned:number,status:string,card:Card};

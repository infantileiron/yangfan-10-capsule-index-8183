/**
 * @typedef {{key:string,label:string,type?:string,optional?:boolean,min?:number,max?:number,choices?:string[]}} Column
 * @typedef {{key:string,label:string,default:number,min:number,max:number,step:number,description:string}} Parameter
 * @typedef {{title:string,subtitle:string,team:string,workflow:string,pain_points:string[],upstream:string,
 * downstream:string,algorithm:string,method:string,columns:Column[],result_columns:Column[],
 * parameter:Parameter,labels:Object,chart:Column,scenario:string[]}} Profile
 */
export function columnNames(columns) {
  return columns.map(column => column.key).join(',');
}

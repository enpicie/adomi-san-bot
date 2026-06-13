output "scheduled_job_function_name" {
  description = "Name of the scheduled job Lambda function"
  value       = module.scheduled_job.lambda_function_name
}
